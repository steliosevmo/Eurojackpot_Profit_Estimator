# Eurojackpot Profit Estimator (Web Scraper)

This script estimates how much Eurojackpot makes after each draw by scraping the official website.  
It was created to enhance my web scraping skills with Selenium and is also inspired by my investment interest in gambling-related stocks (OPAP SA, Flutter Entertainment).

## Features
- Automatically extracts total player stakes
- Extracts prize tiers and winners
- Calculates estimated payout and "profit"
- Adds the essential info in a csv file or updates an existing one

## Disclaimer
This is **not an accurate representation of real profit** since it excludes taxes, marketing, and operational costs.  
The project is educational.

## Technologies
- Python
- Selenium
- Regex

## How to Run
1. Install requirements:
pip install selenium
2. Make sure you have the appropriate `chromedriver`
3. Run the script:
python eurojackpot_scraper.py
