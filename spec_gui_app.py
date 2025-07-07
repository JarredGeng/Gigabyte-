import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import re
import time
import sqlite3
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By

# Path to geckodriver
GECKODRIVER_PATH = "/usr/local/bin/geckodriver"

# Database setup
DB_FILE = "specs.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chassis_specs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            model_name TEXT,
            date_scraped TEXT,
            cpu_socket TEXT,
            cpu_count TEXT,
            max_tdp TEXT,
            total_tdp TEXT,
            memory_type TEXT,
            dimm_slots TEXT,
            power_supply TEXT,
            rack_unit TEXT,
            drive_bays TEXT,
            m2_slots TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_to_db(url, model_name, summary):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO chassis_specs (
            url,
            model_name,
            date_scraped,
            cpu_socket,
            cpu_count,
            max_tdp,
            total_tdp,
            memory_type,
            dimm_slots,
            power_supply,
            rack_unit,
            drive_bays,
            m2_slots
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        url,
        model_name,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        summary.get("CPU Socket"),
        summary.get("CPU Count"),
        summary.get("Max TDP"),
        summary.get("Total TDP"),
        summary.get("Memory Type"),
        summary.get("DIMM Slots"),
        summary.get("Power Supply"),
        summary.get("Rack Unit"),
        summary.get("2.5\" Drive Bays"),
        summary.get("M.2 Slots")
    ))
    conn.commit()
    conn.close()

def export_records_to_excel():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("""
        SELECT
            id,
            date_scraped,
            model_name,
            url,
            cpu_socket,
            cpu_count,
            max_tdp,
            total_tdp,
            memory_type,
            dimm_slots,
            power_supply,
            rack_unit,
            drive_bays,
            m2_slots
        FROM chassis_specs
        ORDER BY id DESC
    """, conn)
    conn.close()
    output_file = "saved_specs.xlsx"
    df.to_excel(output_file, index=False)
    messagebox.showinfo("Export Complete", f"✅ Records exported to {output_file}")

def extract_visible_specs(url):
    options = Options()
    options.headless = False
    options.binary_location = "/Applications/Firefox.app/Contents/MacOS/firefox"

    service = Service(executable_path=GECKODRIVER_PATH)
    driver = webdriver.Firefox(service=service, options=options)

    try:
        driver.get(url)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(10)

        text = None
        try:
            spec_section = driver.find_element(By.ID, "specifications")
            text = spec_section.text.strip()
        except:
            pass

        if not text:
            try:
                spec_section = driver.find_element(By.CLASS_NAME, "specifications")
                text = spec_section.text.strip()
            except:
                pass

        if not text:
            text = driver.find_element(By.TAG_NAME, "body").text.strip()

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

    m2_matches = re.findall(r"\d+\s*x\s*M\.2[^\n]*", text, re.IGNORECASE)
    if m2_matches:
        summary["M.2 Slots"] = f"{len(m2_matches)} detected"

    return summary

def get_specs():
    url = url_entry.get().strip()
    if not url:
        messagebox.showwarning("Missing URL", "Please paste a Gigabyte product URL.")
        return

    # Extract model name
    model_match = re.search(r"/([^/#]+)(?:#|$)", url)
    model_name = model_match.group(1) if model_match else "Unknown"

    # Check for duplicates
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chassis_specs WHERE url=?", (url,))
    existing = cursor.fetchone()
    conn.close()

    for row in output_tree.get_children():
        output_tree.delete(row)

    if existing:
        output_tree.insert("", "end", values=("Notice", "✅ Record already exists"))
        output_tree.insert("", "end", values=("Model Name", existing[2]))
        output_tree.insert("", "end", values=("CPU Socket", existing[4]))
        output_tree.insert("", "end", values=("CPU Count", existing[5]))
        output_tree.insert("", "end", values=("Max TDP", existing[6]))
        output_tree.insert("", "end", values=("Memory Type", existing[8]))
        output_tree.insert("", "end", values=("DIMM Slots", existing[9]))
        output_tree.insert("", "end", values=("Power Supply", existing[10]))
        output_tree.insert("", "end", values=("Rack Unit", existing[11]))
        output_tree.insert("", "end", values=("M.2 Slots", existing[13]))
        return

    output_tree.insert("", "end", values=("Status", "🔄 Fetching specs..."))
    root.update_idletasks()

    try:
        raw_text = extract_visible_specs(url)
        summary = parse_spec_text(raw_text)

        for row in output_tree.get_children():
            output_tree.delete(row)

        if not summary:
            output_tree.insert("", "end", values=("Error", "❌ No specs could be extracted."))
        else:
            output_tree.insert("", "end", values=("Model Name", model_name))
            for k, v in summary.items():
                output_tree.insert("", "end", values=(k, v))
            save_to_db(url, model_name, summary)
            output_tree.insert("", "end", values=("Saved", "✅ specs saved to database"))
    except Exception as e:
        for row in output_tree.get_children():
            output_tree.delete(row)
        output_tree.insert("", "end", values=("Error", f"{e}"))

def view_saved_records():
    records_window = tk.Toplevel(root)
    records_window.title("Saved Chassis Records")
    records_window.geometry("950x500")

    columns = (
        "id", "date", "model_name", "url", "cpu_socket", "cpu_count",
        "max_tdp", "memory_type", "dimm_slots", "power_supply", "rack_unit", "m2_slots"
    )

    tree_frame = tk.Frame(records_window)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
    for col in columns:
        tree.heading(col, text=col.replace("_", " ").title())
        tree.column(col, width=140, anchor=tk.W)

    tree.pack(fill=tk.BOTH, expand=True)

    export_btn = tk.Button(records_window, text="Export to Excel", command=export_records_to_excel)
    export_btn.pack(pady=5)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, date_scraped, model_name, url, cpu_socket, cpu_count,
               max_tdp, memory_type, dimm_slots, power_supply, rack_unit, m2_slots
        FROM chassis_specs
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        tree.insert("", tk.END, values=row)

# Initialize database
init_db()

# GUI Setup
root = tk.Tk()
root.title("Gigabyte Spec Extractor")
root.geometry("750x500")
root.configure(bg="black")

tk.Label(root, text="Paste Gigabyte Product URL:", bg="black", fg="white").pack(pady=8)
url_entry = tk.Entry(root, width=80)
url_entry.pack(pady=5)

button_frame = tk.Frame(root, bg="black")
button_frame.pack(pady=10)

tk.Button(button_frame, text="Get Specs", command=get_specs).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame, text="View Saved Records", command=view_saved_records).pack(side=tk.LEFT, padx=5)

tree_frame = tk.Frame(root)
tree_frame.pack(pady=10, fill=tk.BOTH, expand=True)

tree_scroll = tk.Scrollbar(tree_frame)
tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

output_tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set, columns=("Spec", "Value"), show="headings")
output_tree.heading("Spec", text="Specification")
output_tree.heading("Value", text="Value")
output_tree.column("Spec", width=250, anchor=tk.W)
output_tree.column("Value", width=450, anchor=tk.W)
output_tree.pack(fill=tk.BOTH, expand=True)

tree_scroll.config(command=output_tree.yview)

root.mainloop()

