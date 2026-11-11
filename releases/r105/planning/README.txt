Conditional planning calculation, 11 November 2026

This is a later planning calculation using the existing forwarding pilot, not
new experimental evidence or the original prospective design. Target: 10 pp,
80% marginal power, two-sided normal approximation. The 0.05/8 threshold is
conservative for individual comparisons in the original eight-test family.
It is not exact power for the session-sign permutation procedure, nor the
probability all eight comparisons reject. Training and selection uncertainty
are not included. The JSON lists all assumptions and variance sensitivity.

From this directory, with Python and NumPy:
python forwarding_power_planning.py --root inputs --output recomputed.json

The two inputs retain their original relative paths so the original script
and saved calculation remain byte-identical. No collection, fitting or API
request occurs. The manuscript PDFs have not been changed by this calculation.
