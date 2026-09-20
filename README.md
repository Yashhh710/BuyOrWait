# Buy or Wait?

A frontend-only financial decision calculator. Enter a product, price, and your monthly numbers to receive a deterministic recommendation based on available balance, safety buffer, budget utilization, and monthly surplus.

## Run

Open [frontend/index.html](frontend/index.html) directly in a browser. No Python server, API, package installation, API key, or network connection is required.

The app stores completed analyses in browser `localStorage`. The Sample Scenarios panel provides ready-made inputs, and the local history can be exported as CSV.

## Calculation rules

- Buy now when the price is covered, the remaining balance preserves a safety buffer, and budget utilization is below 85%.
- Buy now with medium risk when the balance is covered and utilization is below 95%.
- Wait and save when monthly surplus is positive.
- Do not proceed when monthly expenses and commitments leave no surplus.

The `backend/` and `data/` folders are retained as the original dataset and server implementation, but the browser app does not use them.
