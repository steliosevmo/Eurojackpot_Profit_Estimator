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
The script doesn't calculate the exact Eurojackpot profits since there are other expenses that I didn't 
include in the substraction(Taxes,Advertisment...). This project was designed to enchanche my webscraping skills. 

I picked this topic since I have invested in gambling stocks (OPAP SA and Flutter Entertainment) 
and I am fascinated by how this industry generates revenue
"""


def setup_driver():
    option = Options() 
    option.add_experimental_option("detach", True)#keep the window open even if the programm ends
    driver_path = "chromedriver-win64\chromedriver-win64\chromedriver.exe"
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service,options=option)
    return driver
    
def find_players_stakes(driver):
    #finds the span that contains the word Stakes so as we can find how much people gambled
    amount_players_gambled= driver.find_elements(By.XPATH,"//span[contains(text(), 'Stakes')]")#returns a list of webelements  
    amount_players_gambled_int=""
    for webelement in amount_players_gambled:
        amount_players_gambled_int+=webelement.text
    amount_players_gambled_int=amount_players_gambled_int.replace("Stakes: €", "").replace(",", "")#replaces text so as to keep only the float number
    amount_players_gambled_int=float(amount_players_gambled_int)
    return amount_players_gambled_int

def extract_payout(driver):
    #for loop 12 winning classes 
    amount_paid_to_players=0
    list_of_winnings=driver.find_elements(By.CLASS_NAME,"winning-amount.right-align")
    queue=[]#it will contain amount of winners and the amount each winner received.
    for web_element in list_of_winnings:
        digits_from_text=re.sub("[^\d\.]","", web_element.text) #regex to clean the text and keep only the digits
        if digits_from_text:#if the string is not empty I turn it into a float
            float_num=float(digits_from_text)
            if float_num>0:
                queue.append(float_num) 
    return list(zip(queue[::2], queue[1::2]))

def calc_payout(payout_data):
    #calculates the amount that was paid to players
    return sum(amount * winners for amount, winners in payout_data)

def extract_date(driver):
    #splits the string that contains all the dates into seperate dates
    date=driver.find_element(By.XPATH,"//select[@formcontrolname='datum']").text.split("\n") 
    return date[0] #most recent date  
    


def write_to_csv(date,total_stakes,total_paid,profit):
    csv_file_path="eurojackpot_profits_webscraping.csv"
    all_dates=set() 
    file_exists=os.path.exists(csv_file_path) #returns true or false if file already exists
    #adds all dates to all_dates set 
    if file_exists:
        with open(csv_file_path,mode='r',newline='') as file:
            reader=csv.DictReader(file)
            for row in reader:
                all_dates.add(row['Date'])
    #if the date already exists in the csv we don't update the csv
    if date in all_dates:
        print(f"We already have data for {date}")
        return 
    #creates the file ,with the appropriate collumn names, if it doesn't exist and appends the data we extracted   
    with open(csv_file_path,mode='a',newline='' ) as file:
        writer=csv.writer(file)
        if not file_exists:
            writer.writerow(["Date","Total Stakes","Total Paid","Profit"])
        writer.writerow([date,f"{total_stakes:,.2f}€",f"{total_paid:,.2f}€",f"{profit:,.2f}€"])



def main():

    driver=setup_driver()
    driver.get("https://www.eurojackpot.com/")

    total_stakes = find_players_stakes(driver)
    payout_data = extract_payout(driver)
    total_paid = calc_payout(payout_data)
    profit = total_stakes - total_paid
    date=extract_date(driver)

    print(date)

    print(f"Eurojackpot's stakes: {total_stakes:,.2f}€")

    print(f"Amount paid to players: {total_paid:,.2f}€")

    print(f"Eurojackpot's profit: {profit:,.2f}€")

    write_to_csv(date,total_stakes,total_paid,profit)



if __name__=="__main__":
    main()




