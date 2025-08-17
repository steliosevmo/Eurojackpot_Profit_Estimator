import selenium
import re 
import csv
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


"""
Stoxos OPAP:
Eurojackpot,Tzoker,Proto,Lotto
Extra 5 , Super 3,Powerspin,Kino 
"""


class Opap_Games:
    def __init__(self,):
        self.driver=Opap_Games.setup_driver()

    def cookies_handler(self):
        cookies_handler=WebDriverWait(self.driver,10).until(EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler"))) #reject cookies 
        cookies_handler.click()
  
    def setup_driver(self):
        option = Options() 
        option.add_experimental_option("detach", True)#keep the window open even if the programm ends
        driver_path = "chromedriver-win64\chromedriver-win64\chromedriver.exe"
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service,options=option)
        return driver
    
    def write_to_csv(self,file_name,date,total_stakes,total_paid,profit):
        csv_file_path=file_name
        all_dates=set() 
        file_exists=os.path.exists(csv_file_path) #returns true or false if file already exists
        #adds all dates to all_dates set 
        if file_exists:
            with open(csv_file_path,mode='r',newline='',encoding="utf-8-sig" ) as file:
                reader=csv.DictReader(file)
                for row in reader:
                    all_dates.add(row['Date'])
        #if the date already exists in the csv we don't update the csv
        if date in all_dates:
            print(f"We already have data for {date}")
            return 
        #creates the file ,with the appropriate collumn names, if it doesn't exist and appends the data we extracted   
        with open(csv_file_path,mode='a',newline='',encoding="utf-8-sig" ) as file:
            writer=csv.writer(file)
            if not file_exists:
                writer.writerow(["Date","Total Stakes","Total Paid","Profit"])
            writer.writerow([date,f"{total_stakes:,.2f}€",f"{total_paid:,.2f}€",f"{profit:,.2f}€"])

    def extract_date(self,driver,draw_date_class="draw-date"):
        #splits the string that contains all the dates into seperate dates
        date=driver.find_element(By.CLASS_NAME,draw_date_class).text.replace("Ημερομηνία","")
        return date #most recent date
    
    def count_earnings(self,driver,earnings_class="draw-winners"):
        amount_of_winners=driver.find_elements(By.CLASS_NAME,"draw-winners")
        queue_winners=[]#it will contain amount of winners and the amount each winner received.
        for web_element in amount_of_winners:
            digits_from_text=re.sub("[^\d,]","", web_element.text)
            if "," in digits_from_text and "." in digits_from_text:
                digits_from_text = digits_from_text.replace(".", "").replace(",", ".")
            elif "," in digits_from_text:
                digits_from_text = digits_from_text.replace(",", ".")
            if digits_from_text:#if the string is not empty I turn it into a float
                float_num=float(digits_from_text)    
                queue_winners.append(float_num)
            
        
        amount_of_winnings=driver.find_elements(By.CLASS_NAME,"draw-amount")
        queue_amounts=[]#it will contain the amount each winner received.
        for web_element in amount_of_winnings:
            digits_from_text=re.sub("[^\d,]","", web_element.text)
            if "," in digits_from_text and "." in digits_from_text:
                digits_from_text = digits_from_text.replace(".", "").replace(",", ".")
            elif "," in digits_from_text:
                digits_from_text = digits_from_text.replace(",", ".")
            if digits_from_text:#if the string is not empty I turn it into a float
                if "," in digits_from_text and "." in digits_from_text:
                    digits_from_text = digits_from_text.replace(".", "").replace(",", ".")
                elif "," in digits_from_text:
                    digits_from_text = digits_from_text.replace(",", ".")
                float_num=float(digits_from_text)
                queue_amounts.append(float_num)
        payout_data=list(zip(queue_winners, queue_amounts))#combines the two lists into a list of tuples
        amount_of_earnings=sum(amount * winners for amount, winners in payout_data)
        return amount_of_earnings 
    def count_stakes(self,driver,stakes_class="draw-columns"):
        total_stakes=driver.find_element(By.CLASS_NAME,stakes_class)
        total_stakes=float(re.sub("[^\d\.]","", total_stakes.text).replace(".",""))
        return total_stakes      


class Tzoker(Opap_Games):
    def __init__(self):
        self.driver=Opap_Games.setup_driver(self)
        self.file_name="tzoker_results.csv"


class Lotto(Opap_Games):
    def __init__(self,):
        self.driver=Opap_Games.setup_driver(self)
        self.file_name="lotto_results.csv"
    def count_earnings(self,driver,earnings_class="draw-winners"):
        elements = driver.find_elements(By.XPATH, "//*[contains(@class, 'draw-winners')]")
        queue_winners=[]#it will contain amount of winners and the amount each winner received.
        
        for web_element in elements:
            if web_element.text=="-":
                queue_winners.append(0)
            else:
                digits_from_text=re.sub("[^\d\.]","", web_element.text).replace(".","")
                if digits_from_text:#if the string is not empty I turn it into a float
                    queue_winners.append(int(digits_from_text))
        for q in queue_winners:
            print(q)
        queue_amounts=[1200000.00,12000.00,30.00,2.00,1.00 ]#the amount opap pays for each category
        payout_data=list(zip(queue_winners, queue_amounts))#combines the two lists into a list of tuples
        amount_of_earnings=sum(winners * amount for winners, amount in payout_data)
        return amount_of_earnings



def main():
    tzoker= Tzoker()
    driver=tzoker.driver
    tzoker.driver.get("https://opaponline.opap.gr/tzoker/draws-results")
    tzoker.cookies_handler()
    total_stakes=tzoker.count_stakes(driver)
    total_paid=tzoker.count_earnings(driver)
    profit = total_stakes - total_paid
    date=tzoker.extract_date(driver)
    print(date)
    print(f"Tzoker's stakes: {total_stakes:,.2f}€")
    print(f"Amount paid to players: {total_paid:,.2f}€")
    print(f"Tzoker's profit: {profit:,.2f}€")
    tzoker.write_to_csv(tzoker.file_name,date,total_stakes,total_paid,profit)

    lotto=Lotto()
    lotto.driver.get("https://opaponline.opap.gr/lotto/draws-results")
    lotto.cookies_handler()
    total_stakes=lotto.count_stakes(lotto.driver,"draw-total-numbers.should-clear.empty-zero.futuran-now-text-400")
    total_paid=lotto.count_earnings(lotto.driver)
    profit = total_stakes - total_paid
    date=lotto.extract_date(lotto.driver,"row-date.should-clear.futuran-now-text-400")
    print(date)
    print(f"Lotto's stakes: {total_stakes:,.2f}€")
    print(f"Amount paid to players: {total_paid:,.2f}€")
    print(f"Lotto's profit: {profit:,.2f}€")
    lotto.write_to_csv(lotto.file_name,date,total_stakes,total_paid,profit)

   
    



if __name__=="__main__":
    main()



    