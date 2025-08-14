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


def setup_driver():
    option = Options() 
    option.add_experimental_option("detach", True)#keep the window open even if the programm ends
    driver_path = "chromedriver-win64\chromedriver-win64\chromedriver.exe"
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service,options=option)
    return driver
    
def cookies_handler(driver):
    cookies_handler=WebDriverWait(driver,10).until(EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler"))) #reject cookies 
    cookies_handler.click()

def count_stakes(driver):
    total_stakes=driver.find_element(By.CLASS_NAME,"draw-columns")
    total_stakes=float(re.sub("[^\d\.]","", total_stakes.text).replace(".",""))
    return total_stakes

def count_earnings(driver):
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
    
    

def main():
    driver=setup_driver()
    driver.get("https://opaponline.opap.gr/tzoker/draws-results")
    cookies_handler(driver)
    
    total_stakes=count_stakes(driver)
    
    total_paid=count_earnings(driver)
    

    profit = total_stakes - total_paid
    
    # date=extract_date(driver)
    # print(date)

    print(f"Tzoker's stakes: {total_stakes:,.2f}€")

    print(f"Amount paid to players: {total_paid:,.2f}€")

    print(f"Tzoker's profit: {profit:,.2f}€")

    # write_to_csv(date,total_stakes,total_paid,profit)



if __name__=="__main__":
    main()