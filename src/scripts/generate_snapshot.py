#!/usr/bin/env python3

'''
This script runs a headless Firefox browser in the background and generates
a publicly accessible Grafana snapshot with a lifetime of 1 hour.
It also stores the URL of this driver in the postgres database, so
Django can access it and redirect users to the URL of the most recent snap
'''

import os
import argparse
import yaml
from datetime import datetime

import psycopg2
import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException


GRAFANA_PWD = os.environ["GRAFANA_PASSWORD"]


def connect_to_postgres(yaml_settings):
    postgres = yaml_settings['postgres_connection']

    kwargs = {
        'host': postgres['host'],
        'port': postgres['port'],
        'database': postgres['dbname'],
        'user': postgres['user'],
        'password': os.environ[postgres['password']]
    }

    if 'sslmode' in postgres:
        kwargs['sslmode'] = postgres['sslmode']
        kwargs['sslrootcert'] = postgres['sslrootcert']
        kwargs['sslcert'] = postgres['sslcert']
        kwargs['sslkey'] = postgres['sslkey']

    postgres_client = psycopg2.connect(**kwargs)
    sys.stderr.write('Connected to the PostgreSQL at {}:{}\n'
                     .format(postgres['host'], postgres['port']))
    return postgres_client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('yaml_settings')
    args = parser.parse_args()

    with open(args.yaml_settings, 'r') as fh:
        yaml_settings = yaml.safe_load(fh)

    options = Options()
    options.set_headless(headless=True)
    driver = webdriver.Firefox(firefox_options=options)
    driver.implicitly_wait(10)
    try:
        driver.get("https://puffer.stanford.edu/grafana/login/")
        driver.find_element_by_name("username").click()
        driver.find_element_by_name("username").clear()
        driver.find_element_by_name("username").send_keys("puffer")
        driver.find_element_by_id("inputPassword").click()
        driver.find_element_by_id("inputPassword").clear()
        driver.find_element_by_id("inputPassword").send_keys(GRAFANA_PWD)
        xpath = ("(.//*[normalize-space(text()) and normalize-space(.)"
                 "='Help'])[1]/following::button[1]")
        driver.find_element_by_xpath(xpath).click()
        xpath = ("(.//*[normalize-space(text()) and normalize-space(.)"
                 "='Help'])[1]/following::i[5]")
        driver.find_element_by_xpath(xpath).click()
        driver.find_element_by_link_text("Snapshot").click()
        xpath = ("(.//*[normalize-space(text()) and normalize-space(.)"
                 "='Expire'])[1]/following::select[1]")
        driver.find_element_by_xpath(xpath).click()
        xpath = ("(.//*[normalize-space(text()) and normalize-space(.)"
                 "='Expire'])[1]/following::select[1]")
        Select(driver.find_element_by_xpath(xpath)).select_by_visible_text("1 Hour")
        xpath = ("(.//*[normalize-space(text()) and normalize-space(.)"
                 "='Expire'])[1]/following::select[1]")
        driver.find_element_by_xpath(xpath).click()
        # begin code to set timeout
        xpath = ("(.//*[normalize-space(text()) and normalize-space(.)"
                 "='Timeout (seconds)'])[1]/following::input[1]")
        driver.find_element_by_xpath(xpath).click()
        xpath = ("(.//*[normalize-space(text()) and normalize-space(.)"
                 "='Timeout (seconds)'])[1]/following::input[1]")
        driver.find_element_by_xpath(xpath).clear()
        xpath = ("(.//*[normalize-space(text()) and normalize-space(.)"
                 "='Timeout (seconds)'])[1]/following::input[1]")
        driver.find_element_by_xpath(xpath).send_keys("300")
        # end code to set timeout
        xpath = ("(.//*[normalize-space(text()) and normalize-space(.)"
                 "='Timeout (seconds)'])[1]/following::button[1]")
        driver.find_element_by_xpath(xpath).click()
        prefix = "https://puffer.stanford.edu/grafana/dashboard/snapshot/"
        snapshot_url = driver.find_element_by_partial_link_text(prefix).text
        print("Generated snapshot: ", snapshot_url)
        driver.quit()
    except NoSuchElementException:
        driver.quit()
        print("Error generating snapshot.")
        return

    # Now, add this link to postgres, and delete old links from the table
    postgres_client = connect_to_postgres(yaml_settings)
    cur = postgres_client.cursor()

    time = datetime.utcnow()
    add_snap_cmd = ("INSERT INTO puffer_grafanasnapshot "
                    "(url, created_on) VALUES (%s, %s)")
    cur.execute(add_snap_cmd, (snapshot_url, time))
    del_old_snap_cmd = "DELETE FROM puffer_grafanasnapshot WHERE (url) != (%s)"
    cur.execute(del_old_snap_cmd, (snapshot_url,))

    conn.commit()
    cur.close()


if __name__ == '__main__':
    main()
