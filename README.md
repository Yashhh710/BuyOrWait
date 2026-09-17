# BuyOrWait — Financial Decision Calculator

> Financial decision tool that helps users decide whether to **BUY, WAIT, or DON'T BUY** a product based on its price and their financial situation.

Built for **HackerRank Orchestrate — September '26**.

---

## Overview

**BuyOrWait** is a simple financial decision-support web application.

The user enters a product and their financial information. The application performs mathematical calculations locally and provides a result:

- **BUY**
- **WAIT**
- **DON'T BUY**

The project uses deterministic mathematical logic instead of AI for the core decision.

---

## Features

### Product Details

- Product name
- Product link
- Product price
- Quantity
- Automatic total price calculation
- Manual price entry fallback

### Financial Analysis

Users can enter:

- Available balance
- Monthly income
- Monthly expenses
- Savings
- Existing monthly commitments

### Decision Analysis

The application calculates:

- Total product cost
- Monthly disposable money
- Money remaining after purchase
- Percentage of available balance used
- Purchase decision

### History

Previous analyses are saved locally using browser `localStorage`.

Users can:

- View previous analyses
- View analysis details
- Delete individual history entries
- Clear all history

### Additional Features

- Try Example
- Recalculate
- Reset
- Input validation
- Download analysis report
- Responsive interface
- Local data storage

---

## How It Works

### 1. Product Information

The user enters:

- Product Name
- Product Link (Optional)
- Price
- Quantity

If a product link is accessible from the browser, the application can attempt to retrieve product information.

If the website blocks browser access, the user can enter the price manually.

The application must never generate or display a fake product price.

### 2. Financial Information

The user enters:

- Available Balance
- Monthly Income
- Monthly Expenses
- Savings
- Existing Monthly Commitments

These values are used for the current calculation.

---

## Mathematical Logic

### Product Total

```text
Product Total = Product Price × Quantity
```

### Monthly Disposable Money

```text
Disposable Money =
Monthly Income
− Monthly Expenses
− Existing Monthly Commitments
```

### Money After Purchase

```text
Money After Purchase =
Available Balance − Product Total
```

### Purchase Percentage

```text
Purchase Percentage =
(Product Total ÷ Available Balance) × 100
```

---

## Decision Logic

### BUY

```text
Product Total ≤ Available Balance
AND
Product Total ≤ Disposable Monthly Money
```

The purchase fits within the user's available balance and calculated monthly disposable money.

### WAIT

```text
Product Total ≤ Available Balance
BUT
Product Total > Disposable Monthly Money
```

The user has enough current balance, but the purchase is relatively large compared with their calculated monthly disposable money.

### DON'T BUY

```text
Product Total > Available Balance
```

The product currently costs more than the user's available balance.

---

## Example

### Input

```text
Product Name:
Sony WH-1000XM5

Price:
₹29,999

Quantity:
1

Available Balance:
₹75,000

Monthly Income:
₹40,000

Monthly Expenses:
₹22,000

Existing Commitments:
₹3,000

Savings:
₹50,000
```

### Calculation

```text
Product Total
= ₹29,999 × 1
= ₹29,999

Disposable Money
= ₹40,000 − ₹22,000 − ₹3,000
= ₹15,000

Money After Purchase
= ₹75,000 − ₹29,999
= ₹45,001

Purchase Percentage
= (₹29,999 ÷ ₹75,000) × 100
≈ 40%
```

Since:

```text
₹29,999 ≤ ₹75,000
BUT
₹29,999 > ₹15,000
```

The result is:

```text
WAIT
```

---

## Application Flow

```text
Product Details
       ↓
Price × Quantity
       ↓
Financial Information
       ↓
Mathematical Calculations
       ↓
Affordability Check
       ↓
BUY / WAIT / DON'T BUY
```

---

## History System

The application stores previous analyses using browser `localStorage`.

Each entry contains:

- Product name
- Product link
- Product price
- Quantity
- Total price
- Available balance
- Monthly income
- Monthly expenses
- Savings
- Existing commitments
- Decision
- Date and time

The newest analysis appears first.

The application stores up to **50 recent analyses**.

---

## Try Example

The **Try Example** button fills the form with sample data so the user can test the application quickly.

Example:

```text
Product:
Sony WH-1000XM5

Price:
₹29,999

Quantity:
1

Available Balance:
₹75,000

Monthly Income:
₹40,000

Monthly Expenses:
₹22,000

Savings:
₹50,000

Commitments:
₹3,000
```

---

## Download Report

The application can generate a local `.txt` report containing:

- Product information
- Financial information
- Calculation results
- Purchase percentage
- Final decision
- Date and time

The report is generated directly in the browser.

No server is required.

---

## Product Link Limitation

A frontend-only website cannot reliably access the price of every e-commerce website.

Some websites use:

- CORS restrictions
- Anti-bot protection
- Dynamic rendering
- Access restrictions

Therefore, the application follows this approach:

```text
Product Link
     ↓
Try to retrieve information
     ↓
Accessible?
   ↙       ↘
 YES       NO
 ↓          ↓
Use data    Manual price entry
```

If the price cannot be retrieved, the user is asked to enter the price manually.

No fake or estimated price is displayed.

---

## Privacy

BuyOrWait does not require:

- User accounts
- Backend servers
- Database
- Financial account connections
- AI APIs
- Financial APIs

Financial information is processed locally in the browser.

History is stored locally using `localStorage`.

---

## Technology Stack

- HTML5
- CSS3
- JavaScript
- Browser `localStorage`

---

## Project Structure

```text
BuyOrWait-Financial-Decision/
│
├── index.html
├── style.css
├── script.js
└── README.md
```

---

## Getting Started

### Clone the Repository

```bash
git clone https://github.com/YOUR-USERNAME/BuyOrWait-Financial-Decision.git
```

### Open the Project

```bash
cd BuyOrWait-Financial-Decision
```

### Run

Open `index.html` in a browser.

You can also use VS Code Live Server.

No backend server is required.

---

## Input Validation

The application validates user input before performing calculations.

- Product name cannot be empty.
- Product price must be greater than `0`.
- Quantity must be greater than `0`.
- Available balance cannot be negative.
- Monthly income cannot be negative.
- Monthly expenses cannot be negative.
- Savings cannot be negative.
- Existing commitments cannot be negative.

The application must never display:

```text
NaN
Infinity
undefined
```

for an invalid calculation.

---

## Reset

The **Reset** button clears:

- Product information
- Price
- Quantity
- Financial information
- Current analysis
- Decision result

History remains saved unless the user selects **Clear History**.

---

## Hackathon

### HackerRank Orchestrate — September '26

**Project:** BuyOrWait

**Concept:** Buy or Wait?

BuyOrWait is a simplified frontend implementation focused on transparent mathematical affordability analysis.

The project demonstrates how user-provided product and financial information can be processed using deterministic calculations to produce a purchase decision.

---

## Project Goals

1. Make purchase calculations simple.
2. Show how a product affects available balance.
3. Compare purchase price with monthly disposable money.
4. Provide a clear BUY, WAIT, or DON'T BUY result.
5. Keep the calculation logic transparent.
6. Keep financial information local.
7. Provide a simple and easy-to-use interface.

---

## Limitations

- Product prices cannot be reliably fetched from every website using frontend-only JavaScript.
- The decision is based only on the information entered by the user.
- The rules are simplified and do not represent a complete financial planning system.
- The application does not connect to bank accounts or financial services.

---

## Disclaimer

BuyOrWait is an educational hackathon project.

The **BUY / WAIT / DON'T BUY** result is generated using predefined mathematical rules and the information entered by the user.

It is not professional financial advice.

---

**Built for HackerRank Orchestrate September '26**
