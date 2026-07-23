import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import os
import json
import sys
from pathlib import Path

try:
    import gspread
    from google.oauth2.service_account import Credentials
    from google.auth.exceptions import GoogleAuthError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

from dotenv import load_dotenv
load_dotenv()

DB_FILE = "database.db"
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS", "credentials.json")
TABLE_NAME = "records"


class Database:
    """قاعدة البيانات المحلية (SQLite)"""

    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()
        self.ensure_table()

    def ensure_table(self):
        self.cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                col1 TEXT,
                col2 TEXT,
                col3 TEXT,
                col4 TEXT,
                col5 TEXT
            )
        """)
        self.conn.commit()

    def get_columns(self):
        return ["col1", "col2", "col3", "col4", "col5"]

    def get_headers(self):
        return ["الاسم", "البريد", "الهاتف", "العنوان", "ملاحظات"]

    def all(self):
        self.cursor.execute(f"SELECT * FROM {TABLE_NAME} ORDER BY id DESC")
        rows = self.cursor.fetchall()
        headers = ["id"] + self.get_columns()
        result = []
        for row in rows:
            result.append(dict(zip(headers, row)))
        return result

    def add(self, data):
        cols = self.get_columns()
        placeholders = ", ".join(["?" for _ in cols])
        self.cursor.execute(
            f"INSERT INTO {TABLE_NAME} ({', '.join(cols)}) VALUES ({placeholders})",
            [data.get(c, "") for c in cols],
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def update(self, record_id, data):
        cols = self.get_columns()
        sets = ", ".join([f"{c}=?" for c in cols])
        self.cursor.execute(
            f"UPDATE {TABLE_NAME} SET {sets} WHERE id=?",
            [data.get(c, "") for c in cols] + [record_id],
        )
        self.conn.commit()

    def delete(self, record_id):
        self.cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE id=?", (record_id,))
        self.conn.commit()

    def search(self, query, column=None):
        if column and column != "الكل":
            sql = f"SELECT * FROM {TABLE_NAME} WHERE {column} LIKE ? ORDER BY id DESC"
            self.cursor.execute(sql, (f"%{query}%",))
        else:
            cols = self.get_columns()
            conditions = " OR ".join([f"{c} LIKE ?" for c in cols])
            sql = f"SELECT * FROM {TABLE_NAME} WHERE {conditions} ORDER BY id DESC"
            self.cursor.execute(sql, [f"%{query}%"] * len(cols))
        rows = self.cursor.fetchall()
        headers = ["id"] + self.get_columns()
        result = []
        for row in rows:
            result.append(dict(zip(headers, row)))
        return result

    def close(self):
        self.conn.close()


class GoogleSheetsDB:
    """قاعدة بيانات Google Sheets"""

    def __init__(self):
        if not GOOGLE_AVAILABLE:
            raise ImportError("المكتبات المطلوبة غير مثبتة: gspread, google-auth")
        if not SHEET_ID or not os.path.exists(CREDENTIALS_FILE):
            raise FileNotFoundError("الملفات المطلوبة غير موجودة: تحقق من .env و credentials.json")
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
        client = gspread.authorize(creds)
        self.sheet = client.open_by_key(SHEET_ID).sheet1

    def get_headers(self):
        try:
            return self.sheet.row_values(1)
        except Exception:
            return ["الاسم", "البريد", "الهاتف", "العنوان", "ملاحظات"]

    def get_columns(self):
        return self.get_headers()

    def ensure_table(self):
        if not self.sheet.row_values(1):
            headers = ["الاسم", "البريد", "الهاتف", "العنوان", "ملاحظات"]
            self.sheet.append_row(headers)

    def all(self):
        records = self.sheet.get_all_records()
        result = []
        for idx, rec in enumerate(records, start=2):
            rec["id"] = idx
            result.append(rec)
        return result

    def add(self, data):
        headers = self.get_headers()
        row = [data.get(h, "") for h in headers]
        self.sheet.append_row(row)

    def update(self, row_id, data):
        headers = self.get_headers()
        for col_idx, h in enumerate(headers, start=1):
            self.sheet.update_cell(row_id, col_idx, data.get(h, ""))

    def delete(self, row_id):
        self.sheet.delete_rows(row_id)

    def search(self, query, column=None):
        all_recs = self.all()
        query = query.strip().lower()
        if not query:
            return all_recs
        result = []
        for rec in all_recs:
            if column and column != "الكل":
                if query in str(rec.get(column, "")).lower():
                    result.append(rec)
            else:
                if any(query in str(v).lower() for v in rec.values()):
                    result.append(rec)
        return result


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("نظام إدارة البيانات - Data Manager")
        self.root.geometry("1100x650")
        self.root.minsize(800, 500)

        self.db = None
        self.data = []
        self.current_mode = tk.StringVar(value="local")
        self.status_var = tk.StringVar(value="جاري التحميل...")

        self.init_database()
        self.setup_ui()
        self.refresh_table()

    def init_database(self):
        try:
            self.db = Database()
            self.status_var.set("قاعدة البيانات المحلية ✓")
            self.current_mode.set("local")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في فتح قاعدة البيانات: {e}")
            self.root.destroy()

    def switch_to_google(self):
        if not GOOGLE_AVAILABLE:
            messagebox.showerror("خطأ", "المكتبات المطلوبة غير مثبتة.\nشغل: pip install gspread google-auth")
            return
        if not SHEET_ID or not os.path.exists(CREDENTIALS_FILE):
            messagebox.showerror(
                "خطأ",
                "الملفات المطلوبة غير موجودة.\n\n"
                "1. أنشئ ملف .env وأضف:\n"
                "   GOOGLE_SHEET_ID=your_sheet_id\n"
                "   GOOGLE_CREDENTIALS=credentials.json\n\n"
                "2. ضع ملف credentials.json في المجلد",
            )
            return
        try:
            gdb = GoogleSheetsDB()
            self.db = gdb
            self.current_mode.set("google")
            self.status_var.set("Google Sheets ✓")
            self.refresh_table()
            messagebox.showinfo("نجاح", "تم الاتصال بـ Google Sheets بنجاح!")
        except Exception as e:
            messagebox.showerror("خطأ في الاتصال", f"فشل الاتصال بـ Google Sheets:\n{e}")

    def switch_to_local(self):
        self.db = Database()
        self.current_mode.set("local")
        self.status_var.set("قاعدة البيانات المحلية ✓")
        self.refresh_table()

    def setup_ui(self):
        # شريط القوائم
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ملف", menu=file_menu)
        file_menu.add_command(label="قاعدة بيانات محلية", command=self.switch_to_local)
        file_menu.add_command(label="Google Sheets", command=self.switch_to_google)
        file_menu.add_separator()
        file_menu.add_command(label="خروج", command=self.root.quit)

        # الإطار العلوي
        top_frame = ttk.Frame(self.root, padding=8)
        top_frame.pack(fill=tk.X)

        ttk.Button(top_frame, text="➕ إضافة", command=self.add_record, width=14).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="✏️ تعديل", command=self.edit_record, width=14).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="🗑️ حذف", command=self.delete_record, width=14).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="🔄 تحديث", command=self.refresh_table, width=14).pack(side=tk.LEFT, padx=2)

        ttk.Label(top_frame, textvariable=self.current_mode, foreground="green").pack(side=tk.RIGHT, padx=10)

        # شريط البحث
        search_frame = ttk.LabelFrame(self.root, text="🔍 بحث", padding=8)
        search_frame.pack(fill=tk.X, padx=8, pady=2)

        ttk.Label(search_frame, text="كلمة البحث:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=35)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind("<KeyRelease>", self.search_records)

        ttk.Label(search_frame, text="في العمود:").pack(side=tk.LEFT, padx=(10, 0))
        self.search_col_var = tk.StringVar(value="الكل")
        self.search_col_combo = ttk.Combobox(
            search_frame, textvariable=self.search_col_var, state="readonly", width=18
        )
        self.search_col_combo.pack(side=tk.LEFT, padx=5)
        self.search_col_combo.bind("<<ComboboxSelected>>", self.search_records)

        ttk.Button(search_frame, text="❌ مسح", command=self.clear_search, width=8).pack(side=tk.LEFT, padx=5)

        # الجدول
        tree_frame = ttk.Frame(self.root, padding=5)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)

        self.tree = ttk.Treeview(
            tree_frame,
            show="headings",
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            selectmode="browse",
        )
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.bind("<Double-1>", lambda e: self.edit_record())
        self.tree.bind("<Return>", lambda e: self.edit_record())
        self.tree.bind("<Delete>", lambda e: self.delete_record())

        self.tree.tag_configure("even", background="#f5f5f5")
        self.tree.tag_configure("odd", background="#ffffff")

        # شريط الحالة
        status_bar = ttk.Frame(self.root, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = ttk.Label(status_bar, textvariable=self.status_var, padding=5)
        self.status_label.pack(side=tk.LEFT)
        ttk.Label(status_bar, text=f"السجلات: ").pack(side=tk.RIGHT, padx=5)
        self.count_label = ttk.Label(status_bar, text="0")
        self.count_label.pack(side=tk.RIGHT)

    def load_columns(self, headers, display_names=None):
        self.tree["columns"] = headers
        for col in headers:
            if display_names and col in display_names:
                text = display_names[col]
            else:
                text = col
            self.tree.heading(col, text=text, command=lambda c=col: self.sort_by_column(c))
            self.tree.column(col, width=120, anchor=tk.CENTER, minwidth=80)

        cols = ["الكل"] + headers
        self.search_col_combo["values"] = cols
        if self.search_col_var.get() not in cols:
            self.search_col_var.set("الكل")

    def sort_by_column(self, col):
        reverse = False
        if hasattr(self, "_last_sort") and self._last_sort == col:
            reverse = True
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        items.sort(key=lambda x: x[0].lower(), reverse=reverse)
        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)
        self._last_sort = col

    def refresh_table(self):
        try:
            self.data = self.db.all()
            self.populate_tree(self.data)
            self.status_var.set(
                f"{'Google Sheets' if self.current_mode.get() == 'google' else 'قاعدة بيانات محلية'} ✓ "
                f"| {len(self.data)} سجل"
            )
            self.count_label.config(text=str(len(self.data)))
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في تحميل البيانات: {e}")

    def populate_tree(self, records):
        for row in self.tree.get_children():
            self.tree.delete(row)
        if not records:
            headers = self.db.get_columns()
            display = dict(zip(headers, self.db.get_headers()))
            self.load_columns(headers, display)
            return
        headers = list(records[0].keys())
        display = {}
        db_headers = self.db.get_headers()
        db_cols = self.db.get_columns()
        for i, col in enumerate(db_cols):
            if col in headers:
                display[col] = db_headers[i] if i < len(db_headers) else col
        self.load_columns(headers, display)
        for i, rec in enumerate(records):
            vals = [str(rec.get(h, "")) for h in headers]
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", tk.END, values=vals, tags=(tag,))

    def get_selected_row_dict(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("تحذير", "الرجاء تحديد سجل أولاً")
            return None
        vals = self.tree.item(sel[0])["values"]
        headers = list(self.tree["columns"])
        return dict(zip(headers, vals))

    def get_id_from_selection(self):
        row = self.get_selected_row_dict()
        if not row:
            return None, None
        return row.get("id"), row

    def add_record(self):
        headers = self.db.get_columns()
        display_names = self.db.get_headers()
        dialog = tk.Toplevel(self.root)
        dialog.title("إضافة سجل جديد")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="إضافة سجل جديد", font=("Arial", 14, "bold")).pack(pady=10)
        ttk.Separator(main_frame).pack(fill=tk.X, pady=5)

        fields_frame = ttk.Frame(main_frame)
        fields_frame.pack(fill=tk.BOTH, expand=True)

        fields = {}
        for i, (col, disp) in enumerate(zip(headers, display_names)):
            ttk.Label(fields_frame, text=disp + ":").grid(
                row=i, column=0, padx=5, pady=5, sticky=tk.W
            )
            e = ttk.Entry(fields_frame, width=45)
            e.grid(row=i, column=1, padx=5, pady=5)
            fields[col] = e

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=15)

        def save():
            data = {c: fields[c].get() for c in headers}
            try:
                self.db.add(data)
                dialog.destroy()
                self.refresh_table()
                messagebox.showinfo("نجاح", "تمت الإضافة بنجاح ✅")
            except Exception as e:
                messagebox.showerror("خطأ", f"فشلت الإضافة: {e}")

        ttk.Button(btn_frame, text="💾 حفظ", command=save, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ إلغاء", command=dialog.destroy, width=12).pack(side=tk.LEFT, padx=5)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

    def edit_record(self):
        row = self.get_selected_row_dict()
        if not row:
            return

        headers = self.db.get_columns()
        display_names = self.db.get_headers()
        record_id = row.get("id")

        dialog = tk.Toplevel(self.root)
        dialog.title("تعديل السجل")
        dialog.geometry("500x420")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="تعديل السجل", font=("Arial", 14, "bold")).pack(pady=10)
        ttk.Separator(main_frame).pack(fill=tk.X, pady=5)

        fields_frame = ttk.Frame(main_frame)
        fields_frame.pack(fill=tk.BOTH, expand=True)

        fields = {}
        for i, (col, disp) in enumerate(zip(headers, display_names)):
            ttk.Label(fields_frame, text=disp + ":").grid(
                row=i, column=0, padx=5, pady=5, sticky=tk.W
            )
            e = ttk.Entry(fields_frame, width=45)
            e.insert(0, str(row.get(col, "")))
            e.grid(row=i, column=1, padx=5, pady=5)
            fields[col] = e

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=15)

        def save():
            data = {c: fields[c].get() for c in headers}
            try:
                if self.current_mode.get() == "google":
                    self.db.update(record_id, data)
                else:
                    self.db.update(record_id, data)
                dialog.destroy()
                self.refresh_table()
                messagebox.showinfo("نجاح", "تم التعديل بنجاح ✅")
            except Exception as e:
                messagebox.showerror("خطأ", f"فشل التعديل: {e}")

        ttk.Button(btn_frame, text="💾 حفظ", command=save, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ إلغاء", command=dialog.destroy, width=12).pack(side=tk.LEFT, padx=5)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

    def delete_record(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("تحذير", "الرجاء تحديد سجل أولاً")
            return
        vals = self.tree.item(sel[0])["values"]
        headers = list(self.tree["columns"])
        row = dict(zip(headers, vals))
        record_id = row.get("id")

        if not messagebox.askyesno(
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف هذا السجل؟\n\n{row.get(headers[1] if len(headers) > 1 else '')}",
            icon="warning",
        ):
            return

        try:
            if self.current_mode.get() == "google":
                self.db.delete(record_id)
            else:
                self.db.delete(record_id)
            self.refresh_table()
            messagebox.showinfo("نجاح", "تم الحذف بنجاح ✅")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل الحذف: {e}")

    def search_records(self, event=None):
        query = self.search_var.get().strip()
        col_filter = self.search_col_var.get()
        if col_filter == "الكل":
            col_filter = None
        elif col_filter == "id":
            col_filter = "id"
        try:
            results = self.db.search(query, col_filter)
            self.populate_tree(results)
            self.count_label.config(text=str(len(results)))
            if query:
                self.status_var.set(f"🔍 نتائج البحث: {len(results)} سجل")
            else:
                self.status_var.set(
                    f"{'Google Sheets' if self.current_mode.get() == 'google' else 'قاعدة بيانات محلية'} ✓ "
                    f"| {len(results)} سجل"
                )
        except Exception as e:
            pass

    def clear_search(self):
        self.search_var.set("")
        self.search_col_var.set("الكل")
        self.refresh_table()


def main():
    root = tk.Tk()
    try:
        root.iconbitmap(default="icon.ico")
    except Exception:
        pass
    app = App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
