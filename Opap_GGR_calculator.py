import re 
import csv
import os
import logging
import random
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


"""
OPAP's Games Finished: Eurojackpot, Tzoker, Lotto
Next steps: Extra 5, Super 3, Powerspin, Kino, Proto
"""

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

class OpapGames:
    """
    Base class for OPAP games. Handles driver setup, cookie handling,
    CSV writing, and common extraction logic.
    """
    def __init__(self):
        self.driver = self.setup_driver()

    def setup_driver(self):
        """Sets up the Chrome WebDriver with anti-detection options."""
        option = Options()
        
        # basic Selenium flags we need to hide
        option.add_experimental_option("excludeSwitches", ["enable-automation"])
        option.add_experimental_option("useAutomationExtension", False)
        option.add_argument("--disable-blink-features=AutomationControlled")
        
        # fullscreen window
        option.add_argument("--start-maximized")

        # Random User-Agent για να μη φαίνεται σαν WebDriver
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]
        option.add_argument(f"--user-agent={random.choice(user_agents)}")

        # Ορισμός διαδρομής chromedriver
        driver_path = os.getenv("CHROMEDRIVER_PATH", "chromedriver-win64\\chromedriver-win64\\chromedriver.exe")
        service = Service(driver_path)

        try:
            driver = webdriver.Chrome(service=service, options=option)

            # Patch στο navigator.webdriver για να μην φαίνεται True
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {
                          get: () => undefined
                        });
                    """
                },
            )

            logging.info("WebDriver started successfully with anti-detection.")
            return driver
        except Exception as e:
            logging.error(f"Failed to start WebDriver: {e}")
            raise


    def cookies_handler(self):
        """Handles cookie consent popup by clicking 'Reject All'."""
        try:
            cookies_handler = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler"))
            )
            cookies_handler.click()
            logging.info("Cookies rejected successfully.")
        except Exception as e:
            logging.warning(f"Cookie handler not found or already handled: {e}")

    def write_to_csv(self, file_name, date, total_stakes, total_paid, profit):
        """
        Writes results to CSV, avoiding duplicate dates.
        """
        csv_file_path = file_name
        all_dates = set()
        file_exists = os.path.exists(csv_file_path)
        if file_exists:
            try:
                with open(csv_file_path, mode='r', newline='', encoding="utf-8-sig") as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        all_dates.add(row['Date'])
            except Exception as e:
                logging.error(f"Error reading CSV: {e}")
        if date in all_dates:
            logging.info(f"We already have data for {date}")
            return
        try:
            with open(csv_file_path, mode='a', newline='', encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                if not file_exists:
                    writer.writerow(["Date", "Total Stakes", "Total Paid", "Profit"])
                writer.writerow([date, f"{total_stakes:,.2f}€", f"{total_paid:,.2f}€", f"{profit:,.2f}€"])
            logging.info(f"Results written to {csv_file_path} for {date}")
        except Exception as e:
            logging.error(f"Error writing to CSV: {e}")

    def extract_date(self, driver, draw_date_class="draw-date"):
        """Extracts the draw date from the page."""
        try:
            date = driver.find_element(By.CLASS_NAME, draw_date_class).text.replace("Ημερομηνία", "")
            return date
        except Exception as e:
            logging.error(f"Could not extract date: {e}")
            return ""

    def count_earnings(self, driver, earnings_class="draw-winners"):
        """
        Calculates the total amount paid to winners.
        """
        try:
            amount_of_winners = driver.find_elements(By.CLASS_NAME, "draw-winners")
            queue_winners = []
            for web_element in amount_of_winners:
                digits_from_text = re.sub("[^\d,]", "", web_element.text)
                if "," in digits_from_text and "." in digits_from_text:
                    digits_from_text = digits_from_text.replace(".", "").replace(",", ".")
                elif "," in digits_from_text:
                    digits_from_text = digits_from_text.replace(",", ".")
                if digits_from_text:
                    float_num = float(digits_from_text)
                    queue_winners.append(float_num)
            amount_of_winnings = driver.find_elements(By.CLASS_NAME, "draw-amount")
            queue_amounts = []
            for web_element in amount_of_winnings:
                digits_from_text = re.sub("[^\d,]", "", web_element.text)
                if "," in digits_from_text and "." in digits_from_text:
                    digits_from_text = digits_from_text.replace(".", "").replace(",", ".")
                elif "," in digits_from_text:
                    digits_from_text = digits_from_text.replace(",", ".")
                if digits_from_text:
                    if "," in digits_from_text and "." in digits_from_text:
                        digits_from_text = digits_from_text.replace(".", "").replace(",", ".")
                    elif "," in digits_from_text:
                        digits_from_text = digits_from_text.replace(",", ".")
                    float_num = float(digits_from_text)
                    queue_amounts.append(float_num)
            payout_data = []
            if len(queue_winners) < len(queue_amounts):
                payout_data = list(zip(queue_winners, queue_amounts[1:]))
            else:
                payout_data = list(zip(queue_winners, queue_amounts))
            amount_of_earnings = sum(amount * winners for amount, winners in payout_data)
            return amount_of_earnings
        except Exception as e:
            logging.error(f"Error calculating earnings: {e}")
            return 0.0

    def count_stakes(self, driver, stakes_class="draw-columns"):
        """Extracts the total stakes from the page."""
        try:
            total_stakes = driver.find_element(By.CLASS_NAME, stakes_class)
            total_stakes = float(re.sub("[^\d\.]", "", total_stakes.text).replace(".", ""))
            return total_stakes
        except Exception as e:
            logging.error(f"Error extracting stakes: {e}")
            return 0.0

class Tzoker(OpapGames):
    """Class for Tzoker game logic."""
    def __init__(self):
        super().__init__()
        self.file_name = "tzoker_results.csv"
    # def until_end(self,):
    #     while(True):
    #         Tzoker().driver.find_element(By.CLASS_NAME, "btn.draw-btn-left").click()



class Lotto(OpapGames):
    """Class for Lotto game logic."""
    def __init__(self):
        super().__init__()
        self.file_name = "lotto_results.csv"

    def count_earnings(self, driver, earnings_class="draw-winners"):
        """
        Calculates Lotto earnings based on fixed prize amounts.
        """
        try:
            elements = driver.find_elements(By.XPATH, "//*[contains(@class, 'draw-winners')]")
            queue_winners = []
            for web_element in elements:
                if web_element.text == "-":
                    queue_winners.append(0)
                else:
                    digits_from_text = re.sub("[^\d\.]", "", web_element.text).replace(".", "")
                    if digits_from_text:
                        queue_winners.append(int(digits_from_text))
            queue_amounts = [1200000.00, 12000.00, 30.00, 2.00, 1.00]
            payout_data = list(zip(queue_winners, queue_amounts))
            amount_of_earnings = sum(winners * amount for winners, amount in payout_data)
            return amount_of_earnings
        except Exception as e:
            logging.error(f"Error calculating Lotto earnings: {e}")
            return 0.0

class Eurojackpot(OpapGames):
    """Class for Eurojackpot game logic."""
    def __init__(self):
        super().__init__()
        self.file_name = "eurojackpot_greece_results.csv"

    def count_stakes(self, driver, stakes_class="slider-details"):
        """
        Extracts and calculates total stakes for Eurojackpot (multiplied by ticket price).
        """
        try:
            total_stakes = driver.find_element(By.CLASS_NAME, stakes_class).text.split("Greece")[1].strip()
            total_stakes = float(re.sub("[^\d\.]", "", total_stakes).replace(".", ""))
            return total_stakes * 2.5
        except Exception as e:
            logging.error(f"Error extracting Eurojackpot stakes: {e}")
            return 0.0

    def count_earnings(self, driver, earnings_class="draw-winners"):
        """
        Calculates Eurojackpot earnings from table data.
        """
        try:
            sum_of_earnings = 0.0
            elements = driver.find_element(By.XPATH, "//tbody")
            elements = elements.text.split("\n")
            for i in elements:
                i = i.split(" ")
                if "JACKPOT" in i:
                    continue
                else:
                    if len(i) > 3:
                        if i[2] == "-":
                            continue
                        num0 = float(re.sub("[^\d.,]", "", i[2]).replace(",", ""))
                        num = float(re.sub("[^\d.,]", "", i[3]).replace(",", ""))
                        sum_of_earnings += num0 * num
                    else:
                        num1 = float(re.sub("[^\d.,]", "", i[1]).replace(",", ""))
                        num2 = float(re.sub("[^\d\.]", "", i[2]))
                        sum_of_earnings += num1 * num2
            return sum_of_earnings
        except Exception as e:
            logging.error(f"Error calculating Eurojackpot earnings: {e}")
            return 0.0

    def extract_date(self):
        """Extracts the draw date for Eurojackpot."""
        try:
            date = self.driver.find_element(By.XPATH, "//p[span[text()='Date']]").text.split("Date")
            return date[1]
        except Exception as e:
            logging.error(f"Could not extract Eurojackpot date: {e}")
            return ""

def main():
    
    """Main function to run the estimations for each game."""
    try:
        tzoker = Tzoker()
        tzoker.driver.get("https://opaponline.opap.gr/tzoker/draws-results")
        tzoker.cookies_handler()
        i=0
        while(i!=2000):
            total_stakes = tzoker.count_stakes(tzoker.driver)
            total_paid = tzoker.count_earnings(tzoker.driver)
            profit = total_stakes - total_paid
            date = tzoker.extract_date(tzoker.driver)
            logging.info(f"Tzoker {date}: Stakes={total_stakes:,.2f}€, Paid={total_paid:,.2f}€, Profit={profit:,.2f}€")
            tzoker.write_to_csv(tzoker.file_name, date, total_stakes, total_paid, profit)    
            WebDriverWait(tzoker.driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "btn.draw-btn-left"))).click()
            i+=1       
        tzoker.driver.quit()

        # lotto = Lotto()
        # lotto.driver.get("https://opaponline.opap.gr/lotto/draws-results")
        # lotto.cookies_handler()
        # total_stakes = lotto.count_stakes(lotto.driver, "draw-total-numbers.should-clear.empty-zero.futuran-now-text-400")
        # total_paid = lotto.count_earnings(lotto.driver)
        # profit = total_stakes - total_paid
        # date = lotto.extract_date(lotto.driver, "row-date.should-clear.futuran-now-text-400")
        # logging.info(f"Lotto {date}: Stakes={total_stakes:,.2f}€, Paid={total_paid:,.2f}€, Profit={profit:,.2f}€")
        # lotto.write_to_csv(lotto.file_name, date, total_stakes, total_paid, profit)
        # lotto.driver.quit()

        # eurojackpot = Eurojackpot()
        # eurojackpot.driver.get("https://www.opap.gr/en/eurojackpot-draw-results")
        # eurojackpot.cookies_handler()
        # total_stakes = eurojackpot.count_stakes(eurojackpot.driver)
        # total_paid = eurojackpot.count_earnings(eurojackpot.driver)
        # profit = total_stakes - total_paid
        # date = eurojackpot.extract_date()
        # logging.info(f"Eurojackpot {date}: Stakes={total_stakes:,.2f}€, Paid={total_paid:,.2f}€, Profit={profit:,.2f}€")
        # eurojackpot.write_to_csv(eurojackpot.file_name, date, total_stakes, total_paid, profit)
        # eurojackpot.driver.quit()
    except Exception as e:
        logging.critical(f"Critical error in main: {e}")

if __name__ == "__main__":
    main()



