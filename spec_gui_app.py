import tkinter as tk
from tkinter import scrolledtext, messagebox
import pandas as pd
import re
import time
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By

# Path to geckodriver
GECKODRIVER_PATH = "/usr/local/bin/geckodriver"

def extract_visible_specs(url):
    options = Options()
    options.headless = False  # Show Firefox for debugging
    options.binary_location = "/Applications/Firefox.app/Contents/MacOS/firefox"

    service = Service(executable_path=GECKODRIVER_PATH)
    driver = webdriver.Firefox(service=service, options=options)

    try:
        driver.get(url)

        # Wait 5 seconds for JavaScript
        time.sleep(5)

        try:
            spec_section = driver.find_element(By.ID, "specifications")
            text = spec_section.text
        except:
            # Fallback: get entire body text
            text = driver.find_element(By.TAG_NAME, "body").text

        # Save HTML for inspection
        with open("dump.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)

    finally:
        driver.quit()

    return text

def parse_spec_text(text):
    summary = {}
    cpu_count = 1
    max_tdp = None

    socket_match = re.search(r"(LGA\s*\d{4})(.*?Socket\s*\w+)?", text, re.IGNORECASE)
    if socket_match:
        socket_str = socket_match.group(1)
        if socket_match.group(2):
            socket_str += " " + socket_match.group(2).strip()
        summary["CPU Socket"] = socket_str.strip()

    tdp_match = re.search(r"(\d{2,4})\s*[wW].*?TDP", text, re.IGNORECASE)
    if not tdp_match:
        tdp_match = re.search(r"TDP.*?(\d{2,4})\s*[wW]", text, re.IGNORECASE)
    if tdp_match:
        max_tdp = int(tdp_match.group(1))
        summary["Max TDP"] = f"{max_tdp}W"

    cpu_count_match = re.search(r"(single|dual|quad|2|4)[-\s]*(processor|cpu)", text, re.IGNORECASE)
    if cpu_count_match:
        val = cpu_count_match.group(1).lower()
        if val in ["dual", "2"]:
            cpu_count = 2
        elif val in ["quad", "4"]:
            cpu_count = 4
    summary["CPU Count"] = str(cpu_count)
    if max_tdp:
        summary["Total TDP"] = f"{max_tdp * cpu_count}W"

    mem_match = re.search(r"(ddr[345][^\n]*)", text, re.IGNORECASE)
    if mem_match:
        summary["Memory Type"] = mem_match.group(1)

    dimm_match = re.search(r"(\d+)\s*x\s*dimm", text, re.IGNORECASE)
    if dimm_match:
        summary["DIMM Slots"] = dimm_match.group(1)

    psu_match = re.search(r"(\d+)\s*x\s*(\d{3,4})\s*w", text, re.IGNORECASE)
    if psu_match:
        count = int(psu_match.group(1))
        watts = psu_match.group(2)
        summary["Power Supply"] = f"{count} x {watts}W"

    rack_match = re.search(r"\b([1-8][Uu])\b", text)
    if rack_match:
        summary["Rack Unit"] = rack_match.group(1).upper()

    bay_match = re.search(r"(\d+)\s*x\s*2.5.*?(nvme|sata)", text, re.IGNORECASE)
    if bay_match:
        summary["2.5\" Drive Bays"] = bay_match.group(1)

    return summary

def get_specs():
    url = url_entry.get().strip()
    if not url:
        messagebox.showwarning("Missing URL", "Please paste a Gigabyte product URL.")
        return

    output_box.delete("1.0", tk.END)
    output_box.insert(tk.END, "🔄 Fetching specs...\n")

    try:
        raw_text = extract_visible_specs(url)
        summary = parse_spec_text(raw_text)
        if not summary:
            output_box.insert(tk.END, "\n❌ No specs could be extracted.")
        else:
            output_box.insert(tk.END, "\n📋 Extracted Summary:\n")
            output_box.insert(tk.END, "-" * 35 + "\n")
            for k, v in summary.items():
                output_box.insert(tk.END, f"{k:<25}: {v}\n")
            output_box.insert(tk.END, "-" * 35 + "\n")
            pd.DataFrame([summary]).to_csv("specs_from_rendered_text.csv", index=False)
            output_box.insert(tk.END, "✅ Saved to specs_from_rendered_text.csv\n")
    except Exception as e:
        output_box.insert(tk.END, f"\n❌ Error: {e}")

# GUI Setup
root = tk.Tk()
root.title("Gigabyte Spec Extractor")
root.geometry("700x500")
root.configure(bg="black")

tk.Label(root, text="Paste Gigabyte Product URL:", bg="black", fg="white").pack(pady=8)
url_entry = tk.Entry(root, width=80)
url_entry.pack(pady=5)

tk.Button(root, text="Get Specs", command=get_specs).pack(pady=10)

output_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=80, height=20, bg="white", fg="black")
output_box.pack(pady=10)

root.mainloop()
