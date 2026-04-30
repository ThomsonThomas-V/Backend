#!/usr/bin/env python3
"""
Unit‑Converter web app (Flask)

Routes:
    /length      → length conversion page
    /weight      → weight conversion page
    /temperature → temperature conversion page
"""

from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)

# ----------------------------------------------------------------------
# Conversion tables – everything is expressed in a *base* unit
# ----------------------------------------------------------------------
# Length: base = metre (m)
LENGTH_FACTORS = {
    "mm": 0.001,          # millimetre → metre
    "cm": 0.01,           # centimetre → metre
    "m": 1.0,             # metre → metre
    "km": 1000.0,         # kilometre → metre
    "in": 0.0254,         # inch → metre
    "ft": 0.3048,         # foot → metre
    "yd": 0.9144,         # yard → metre
    "mi": 1609.344,       # mile → metre
}

# Weight: base = gram (g)
WEIGHT_FACTORS = {
    "mg": 0.001,          # milligram → gram
    "g": 1.0,             # gram → gram
    "kg": 1000.0,         # kilogram → gram
    "oz": 28.349523125,   # ounce → gram
    "lb": 453.59237,      # pound → gram
}

# Temperature: base = Kelvin (K) – not a simple factor, we need functions
def c_to_k(c): return c + 273.15
def k_to_c(k): return k - 273.15
def f_to_k(f): return (f + 459.67) * 5/9
def k_to_f(k): return k * 9/5 - 459.67

# ----------------------------------------------------------------------
# Helpers that do the heavy lifting
# ----------------------------------------------------------------------
def convert(value: float, from_u: str, to_u: str, factors: dict) -> float:
    """
    General linear conversion using a factor table.
    value   – numeric value entered by the user
    from_u  – unit we are converting *from*
    to_u    – unit we are converting *to*
    factors – dict mapping unit → factor (relative to the base unit)
    """
    # 1) Convert *from* unit → base unit
    base_val = value * factors[from_u]
    # 2) Convert base unit → *to* unit
    return base_val / factors[to_u]


def temp_convert(value: float, from_u: str, to_u: str) -> float:
    """
    Temperature conversion – uses Kelvin as the pivot.
    """
    # 1) Bring user value to Kelvin
    if from_u == "C":
        k = c_to_k(value)
    elif from_u == "F":
        k = f_to_k(value)
    elif from_u == "K":
        k = value
    else:
        raise ValueError(f"Unsupported temperature unit {from_u}")

    # 2) Convert from Kelvin to target unit
    if to_u == "C":
        return k_to_c(k)
    elif to_u == "F":
        return k_to_f(k)
    elif to_u == "K":
        return k
    else:
        raise ValueError(f"Unsupported temperature unit {to_u}")


# ----------------------------------------------------------------------
# Routes – each page works the same way
# ----------------------------------------------------------------------
@app.route("/")
def home():
    """Redirect to the first section (Length)"""
    return redirect(url_for("length"))


# ------------------ Length ------------------
@app.route("/length", methods=["GET", "POST"])
def length():
    result = None
    if request.method == "POST":
        try:
            val = float(request.form["value"])
            from_u = request.form["from"]
            to_u   = request.form["to"]
            result = convert(val, from_u, to_u, LENGTH_FACTORS)
        except (ValueError, KeyError) as e:
            result = f"❌  Invalid input: {e}"

    return render_template(
        "length.html",
        units=sorted(LENGTH_FACTORS.keys()),
        result=result,
        now=datetime.now
    )


# ------------------ Weight ------------------
@app.route("/weight", methods=["GET", "POST"])
def weight():
    result = None
    if request.method == "POST":
        try:
            val = float(request.form["value"])
            from_u = request.form["from"]
            to_u   = request.form["to"]
            result = convert(val, from_u, to_u, WEIGHT_FACTORS)
        except (ValueError, KeyError) as e:
            result = f"❌  Invalid input: {e}"

    return render_template(
        "weight.html",
        units=sorted(WEIGHT_FACTORS.keys()),
        result=result,
        now=datetime.now
    )


# ------------------ Temperature ------------------
@app.route("/temperature", methods=["GET", "POST"])
def temperature():
    result = None
    if request.method == "POST":
        try:
            val = float(request.form["value"])
            from_u = request.form["from"]
            to_u   = request.form["to"]
            result = temp_convert(val, from_u, to_u)
        except (ValueError, KeyError) as e:
            result = f"❌  Invalid input: {e}"

    # Temperature units are fixed, no need for a dict
    temp_units = ["C", "F", "K"]
    return render_template(
        "temperature.html",
        units=temp_units,
        result=result,
        now=datetime.now
    )


# ----------------------------------------------------------------------
# Run the application
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # Use debug=True while developing; switch to False for production
    app.run(debug=True)
