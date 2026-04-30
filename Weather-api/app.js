// ---------------------------------------------------------------
// weather API – Express server with Redis cache, env vars,
// rate limiting and error handling.
// ---------------------------------------------------------------
require('dotenv').config();                       // load .env
const express   = require('express');
const axios     = require('axios');
const { createClient } = require('redis');
const rateLimit = require('express-rate-limit');
const morgan    = require('morgan');

const app = express();
const PORT = process.env.PORT || 3000;

// ---------------------------------------------------------------
// 1️⃣  Redis client (v4) – single connection, reused everywhere
// ---------------------------------------------------------------
const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';
const redis = createClient({ url: redisUrl });

redis.on('error', err => console.error('Redis error →', err));

(async () => {
    try {
        await redis.connect();
        console.log('✅  Connected to Redis at', redisUrl);
    } catch (e) {
        console.error('❌  Could not connect to Redis – cache disabled', e);
    }
})();

// ---------------------------------------------------------------
// 2️⃣  Middleware
// ---------------------------------------------------------------
app.use(express.json());        // not strictly needed for GET but nice to have
app.use(morgan('combined'));   // request logging

// ----- Rate limiter (default: 60 req / minute per IP, configurable via .env)
const limiter = rateLimit({
    windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS) || 60_000, // 1 min
    max:      parseInt(process.env.RATE_LIMIT_MAX)     || 60,      // 60 req per window
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: 'Too many requests – please slow down.' }
});
app.use(limiter);

// ---------------------------------------------------------------
// 3️⃣  Helper: build Visual Crossing request URL
// ---------------------------------------------------------------
const VC_API_KEY = process.env.VC_API_KEY?.trim(); // may be empty for stub
const VC_BASE_URL = 'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline';

function buildVcUrl(city) {
    // Visual Crossing syntax: /{location}/{date}?key=YOUR_API_KEY&unitGroup=metric&include=days
    const encodedCity = encodeURIComponent(city);
    const today = new Date().toISOString().split('T')[0]; // YYYY‑MM‑DD
    const params = new URLSearchParams({
        key: VC_API_KEY,
        unitGroup: 'metric',
        include: 'days',
        contentType: 'json'
    });
    return `${VC_BASE_URL}/${encodedCity}/${today}?${params.toString()}`;
}

// ---------------------------------------------------------------
// 4️⃣  Helper: hard‑coded fallback (used when VC_API_KEY missing)
// ---------------------------------------------------------------
function stubWeather(city) {
    // Very tiny payload – just enough to illustrate the shape
    return {
        location: city,
        current: {
            temp: 20,
            description: 'Clear sky',
            humidity: 60,
            windSpeed: 5
        },
        forecast: []   // could fill with dummy data if you wish
    };
}

// ---------------------------------------------------------------
// 5️⃣  Main endpoint – GET /weather?city=<city>
// ---------------------------------------------------------------
app.get('/weather', async (req, res) => {
    const city = (req.query.city || '').trim();

    if (!city) {
        return res.status(400).json({ error: 'Missing required query param: city' });
    }

    const cacheKey = `weather:${city.toLowerCase()}`;

    // -----------------------------------------------------------------
    // 5.1  Try cache first
    // -----------------------------------------------------------------
    try {
        const cached = await redis.get(cacheKey);
        if (cached) {
            // Cache hit – serve immediately
            return res.json({ source: 'cache', data: JSON.parse(cached) });
        }
    } catch (e) {
        // If Redis is down we just log, but we don’t abort the request.
        console.warn('Redis read error (ignored) →', e.message);
    }

    // -----------------------------------------------------------------
    // 5.2  No cache – call external API (or return stub)
    // -----------------------------------------------------------------
    let weatherData;
    if (!VC_API_KEY) {
        // No API key → use stub data – useful for local dev or CI pipelines
        weatherData = stubWeather(city);
    } else {
        // Build the request URL
        const url = buildVcUrl(city);
        try {
            const { data } = await axios.get(url, { timeout: 8000 }); // 8 s timeout

            // Visual Crossing returns a *lot* of fields – we trim to something nicer:
            weatherData = {
                location: data.resolvedAddress,
                current: {
                    temp: data.currentConditions.temp,
                    description: data.currentConditions.conditions,
                    humidity: data.currentConditions.humidity,
                    windSpeed: data.currentConditions.windspeed
                },
                // You could also expose a short 3‑day forecast here if you like
                forecast: (data.days || []).slice(0, 3).map(d => ({
                    date: d.datetime,
                    tempHigh: d.tempmax,
                    tempLow: d.tempmin,
                    description: d.conditions
                }))
            };
        } catch (apiErr) {
            // -------------------------------------------------------------
            // 5.3  API call failed – figure out why
            // -------------------------------------------------------------
            if (apiErr.response) {
                // 3xx/4xx/5xx from Visual Crossing
                const status = apiErr.response.status;
                const msg = apiErr.response.data?.message || apiErr.response.statusText;
                return res.status(status).json({
                    error: `Weather provider returned ${status}: ${msg}`
                });
            } else if (apiErr.code === 'ECONNABORTED') {
                // Timeout
                return res.status(504).json({ error: 'Weather provider timed out' });
            } else {
                // Network or unknown error
                console.error('Unexpected error while calling VC API →', apiErr);
                return res.status(502).json({ error: 'Unable to reach weather provider' });
            }
        }
    }

    // -----------------------------------------------------------------
    // 5.4  Store the fresh result in Redis (12 h TTL)
    // -----------------------------------------------------------------
    try {
        await redis.set(cacheKey, JSON.stringify(weatherData), {
            EX: 12 * 60 * 60   // 12 hours in seconds
        });
    } catch (e) {
        console.warn('Redis write error (ignored) →', e.message);
        // We still respond to the client – caching is best‑effort.
    }

    // -----------------------------------------------------------------
    // 5.5  Return the fresh payload
    // -----------------------------------------------------------------
    res.json({ source: VC_API_KEY ? 'api' : 'stub', data: weatherData });
});

// ---------------------------------------------------------------
// 6️⃣  Health‑check endpoint (handy for orchestration)
// ---------------------------------------------------------------
app.get('/health', async (req, res) => {
    const redisOk = await redis.ping().catch(() => false);
    res.json({
        status: 'ok',
        redis: redisOk ? 'connected' : 'unavailable',
        rateLimit: {
            windowMs: limiter.windowMs,
            max: limiter.max
        }
    });
});

// ---------------------------------------------------------------
// 7️⃣  404 handler
// ---------------------------------------------------------------
app.use((req, res) => {
    res.status(404).json({ error: 'Endpoint not found' });
});

// ---------------------------------------------------------------
// 8️⃣  Global error handler (fallback)
// ---------------------------------------------------------------
app.use((err, req, res, next) => {
    console.error('Unhandled error →', err);
    res.status(500).json({ error: 'Internal server error' });
});

// ---------------------------------------------------------------
// 9️⃣  Start the server
// ---------------------------------------------------------------
app.listen(PORT, () => {
    console.log(`🚀  Weather API listening on http://localhost:${PORT}`);
});
