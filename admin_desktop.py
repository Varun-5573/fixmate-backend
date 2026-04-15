import customtkinter as ctk
import threading
import requests
import json
import time
import webbrowser
import csv
import os
import shutil
import random
from tkinter import filedialog
from datetime import datetime

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

def start_server():
    try:
        from server import app
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except: pass

class FixMateApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FixMate Native Admin Pro v4 - Chatbot Support")
        self.geometry("1450x850")
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.last_data_hash = ""
        self.current_view = ""
        self.search_query = ""
        self.bookings_cache = []
        self.workers_cache = {}
        self.tickets_cache = []
        self.chat_messages_cache = []
        
        # --- Sidebar ---
        self.sidebar = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color="#0A0F1C")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo = ctk.CTkLabel(self.sidebar, text="🚀 FixMate Enterprise", font=ctk.CTkFont(size=22, weight="bold"), text_color="#A78BFA")
        self.logo.grid(row=0, column=0, padx=20, pady=(30, 40))
        
        # Navigation Buttons
        self.btn_dash = self.create_nav_btn("📊 Dashboard", "dashboard", 1)
        self.btn_bookings = self.create_nav_btn("📋 Live Bookings", "bookings", 2)
        self.btn_workers = self.create_nav_btn("👷 Manage Workers", "workers", 3)
        self.btn_tickets = self.create_nav_btn("🎫 Support Tickets", "tickets", 4)
        self.btn_chat = self.create_nav_btn("💬 Live Chat Support", "chat", 5)
        self.btn_system = self.create_nav_btn("⚙️ Settings & Backups", "system", 6)
        
        self.btn_add_worker = ctk.CTkButton(self.sidebar, text="➕ Add Worker", font=("Inter", 16, "bold"), fg_color="#10B981", hover_color="#059669", height=45, command=self.open_add_worker)
        self.btn_add_worker.grid(row=7, column=0, padx=20, pady=20, sticky="ew")
        
        self.btn_export = ctk.CTkButton(self.sidebar, text="📥 Export CSV Data", font=("Inter", 16, "bold"), fg_color="#3B82F6", hover_color="#2563EB", height=45, command=self.export_csv)
        self.btn_export.grid(row=8, column=0, padx=20, pady=0, sticky="ew")
        
        self.status_lbl = ctk.CTkLabel(self.sidebar, text="Server: ONLINE 🟢", text_color="#10B981", font=("Inter", 12, "bold"))
        self.status_lbl.grid(row=9, column=0, pady=20, sticky="s")
        
        # --- Main Frame ---
        self.main_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="#111827")
        self.main_frame.grid(row=0, column=1, padx=25, pady=25, sticky="nsew")
        
        # --- Header Search & Bar ---
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent", height=60)
        self.header_frame.pack(fill="x", padx=30, pady=(20, 0))
        self.title_lbl = ctk.CTkLabel(self.header_frame, text="", font=ctk.CTkFont(size=30, weight="bold"), text_color="white")
        self.title_lbl.pack(side="left")
        
        self.search_entry = ctk.CTkEntry(self.header_frame, placeholder_text="🔍 Search Engine...", width=300, font=("Inter", 14))
        self.search_entry.pack(side="right")
        self.search_entry.bind("<KeyRelease>", self.on_search)

        self.content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)
        
        self.switch_view("dashboard")
        self.after(1000, self.auto_refresh)

    def create_nav_btn(self, text, view, row):
        btn = ctk.CTkButton(self.sidebar, text=text, font=("Inter", 16), height=45, anchor="w", fg_color="transparent", text_color="#FFFFFF", command=lambda v=view: self.switch_view(v))
        btn.grid(row=row, column=0, padx=20, pady=5, sticky="ew")
        return btn

    def on_search(self, event):
        self.search_query = self.search_entry.get().lower()
        self.render_current_view()

    def post_action(self, params):
        try:
            requests.post("http://127.0.0.1:5000/admin", data=params, timeout=5)
            self.last_data_hash = ""
            self.get_data_bg()
            self.show_toast("Action executed successfully!")
        except: self.show_toast("Error: Backend disconnected!")

    def show_toast(self, message):
        t = ctk.CTkToplevel(self)
        t.overrideredirect(True)
        t.geometry(f"300x50+{self.winfo_x() + self.winfo_width() - 320}+{self.winfo_y() + 50}")
        t.attributes("-topmost", True)
        f = ctk.CTkFrame(t, fg_color="#10B981", corner_radius=10)
        f.pack(fill="both", expand=True)
        ctk.CTkLabel(f, text=message, font=("Inter", 14, "bold"), text_color="white").pack(pady=15)
        self.after(2500, t.destroy)

    CLOUD = "https://fixmate-backend-68dy.onrender.com"
    _fetching = False

    def get_data_bg(self):
        """Fetch data in background thread — never blocks UI"""
        if self._fetching:
            return
        self._fetching = True
        def _fetch():
            try:
                local_b = []
                w = {}
                try:
                    local_b = requests.get("http://127.0.0.1:5000/api/bookings", timeout=3).json()
                    w = requests.get("http://127.0.0.1:5000/api/workers", timeout=3).json()
                except: pass

                # Cloud bookings (phone books via cloud)
                try:
                    cloud_b = requests.get(f"{self.CLOUD}/api/bookings", timeout=10).json()
                    cloud_ids = {bk['id'] for bk in cloud_b}
                    extra = [bk for bk in local_b if bk.get('id') not in cloud_ids]
                    b = cloud_b + extra
                except:
                    b = local_b

                # Support tickets from cloud
                cloud_tickets = []
                try:
                    cloud_tickets = requests.get(f"{self.CLOUD}/api/support", timeout=25).json()
                    if isinstance(cloud_tickets, dict): cloud_tickets = []
                except: pass

                # Load any locally saved tickets too (survive Render restarts)
                local_ticket_path = "support_local.json"
                try:
                    with open(local_ticket_path, 'r', encoding='utf-8') as f:
                        local_tickets = json.load(f)
                except: local_tickets = []

                # Merge: cloud tickets + any local-only ones not on cloud yet
                cloud_ids_t = {tk['id'] for tk in cloud_tickets}
                merged = cloud_tickets + [lt for lt in local_tickets if lt.get('id') not in cloud_ids_t]

                # Save merged list locally so tickets survive Render sleep
                if merged:
                    try:
                        with open(local_ticket_path, 'w', encoding='utf-8') as f:
                            json.dump(merged, f, indent=2)
                    except: pass

                t = merged

                curr_hash = json.dumps(b) + json.dumps(w) + json.dumps(t)
                
                # Fetch chatbot messages from cloud
                chat_msgs = []
                try:
                    chat_msgs = requests.get(f"{self.CLOUD}/api/admin/messages", timeout=10).json()
                except: pass

                curr_hash = json.dumps(b) + json.dumps(w) + json.dumps(t) + json.dumps(chat_msgs)
                if curr_hash != self.last_data_hash:
                    self.last_data_hash = curr_hash
                    self.bookings_cache = b
                    self.workers_cache = w
                    self.tickets_cache = t
                    self.chat_messages_cache = chat_msgs
                    self.after(0, self.render_current_view)
            except: pass
            finally:
                self._fetching = False
        threading.Thread(target=_fetch, daemon=True).start()

    def switch_view(self, view_name):
        self.current_view = view_name
        self.search_query = ""
        self.search_entry.delete(0, 'end')
        if view_name in ["dashboard", "system"]:
            self.search_entry.pack_forget()
        else:
            self.search_entry.pack(side="right")
        self.last_data_hash = ""  # Force refresh
        self.render_current_view()  # Show existing cache immediately
        self.get_data_bg()          # Then fetch fresh data in background

    def auto_refresh(self):
        """Trigger background fetch every 5 seconds — UI never blocks"""
        self.get_data_bg()
        self.after(5000, self.auto_refresh)

    def render_current_view(self):
        for widget in self.content_frame.winfo_children(): widget.destroy()
        for btn in [self.btn_dash, self.btn_bookings, self.btn_workers, self.btn_tickets, self.btn_chat, self.btn_system]: btn.configure(fg_color="transparent")
        
        if self.current_view == "dashboard":
            self.btn_dash.configure(fg_color="#8B5CF6")
            self.title_lbl.configure(text="📊 Activity Dashboard")
            self.render_dashboard(self.bookings_cache, self.workers_cache)
        elif self.current_view == "bookings":
            self.btn_bookings.configure(fg_color="#8B5CF6")
            self.title_lbl.configure(text="📋 Advanced Booking Engine")
            self.render_bookings(self.bookings_cache)
        elif self.current_view == "system":
            self.btn_system.configure(fg_color="#8B5CF6")
            self.title_lbl.configure(text="⚙️ DB Settings & Backups")
            self.render_system()
        elif self.current_view == "tickets":
            self.btn_tickets.configure(fg_color="#8B5CF6")
            self.title_lbl.configure(text="🎫 Customer Support Chatbot Logs")
            self.render_tickets(self.tickets_cache)
        elif self.current_view == "chat":
            self.btn_chat.configure(fg_color="#8B5CF6")
            self.title_lbl.configure(text="💬 Live Chat Support")
            self.render_chat(self.chat_messages_cache)
        else:
            self.btn_workers.configure(fg_color="#8B5CF6")
            self.title_lbl.configure(text="👷 Central Worker Hub")
            self.render_workers(self.workers_cache)

    def render_dashboard(self, bookings, workers_dict):
        grid = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        grid.pack(fill="x", padx=30, pady=20)
        
        pending = sum(1 for b in bookings if b.get('status') == 'Pending')
        accepted = sum(1 for b in bookings if b.get('status') == 'Accepted')
        revenue = accepted * 150 
        
        total_workers = sum(len(v) for v in workers_dict.values())
        online_workers = sum(1 for v in workers_dict.values() for w in v if w.get('isOnline'))
        
        self.create_stat_card(grid, "Pending Requests", str(pending), "#F59E0B", "orange")
        self.create_stat_card(grid, "Completed Jobs", str(accepted), "#10B981", "green")
        self.create_stat_card(grid, "Active Workers", f"{online_workers} / {total_workers}", "#3B82F6", "blue")
        self.create_stat_card(grid, "Gross Revenue", f"₹{revenue}", "#8B5CF6", "purple")

    def create_stat_card(self, parent, title, value, color, _type):
        card = ctk.CTkFrame(parent, corner_radius=15, width=240, height=140, fg_color="#1F2937", border_width=2, border_color=color)
        card.pack(side="left", padx=15, expand=True, fill="both")
        card.pack_propagate(False)
        ctk.CTkLabel(card, text=title, font=("Inter", 16), text_color="#9CA3AF").pack(pady=(25,5))
        ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=45, weight="bold"), text_color=color).pack()

    def auto_assign(self, booking_id, required_service):
        online = [w for v in self.workers_cache.values() for w in v if w.get('isOnline') and w['serviceType'].lower() == required_service.lower()]
        if not online:
            self.show_toast("No online workers available for this service!")
            return
        chosen = random.choice(online)
        try:
            self.post_action({"action": "update_booking_status", "booking_id": booking_id, "status": "Accepted"})
            self.show_toast(f"🤖 AI Assigned to: {chosen['name']}")
        except: pass

    def render_bookings(self, bookings):
        scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)
        filtered = [b for b in bookings if self.search_query in json.dumps(b).lower()] if self.search_query else bookings
        for b in filtered:
            state_col = "#F59E0B" if b.get('status')=='Pending' else "#10B981" if b.get('status')=='Accepted' else "#EF4444"
            c = ctk.CTkFrame(scroll, corner_radius=12, fg_color="#1E293B", border_width=2, border_color=state_col)
            c.pack(fill="x", padx=10, pady=10)
            
            inf = ctk.CTkFrame(c, fg_color="transparent")
            inf.pack(side="left", fill="both", expand=True, padx=20, pady=15)
            ctk.CTkLabel(inf, text=f"👤 {b.get('customer_name')}    →    👷 {b.get('worker_name')} ({b.get('service')})", font=ctk.CTkFont(size=18, weight="bold"), text_color="white").pack(anchor="w")
            det = f"📞 {b.get('customer_phone')}   |   📍 {b.get('customer_address')}   |   🗓️ {b.get('date')} at {b.get('time')}   |   🔖 {b.get('status')}"
            ctk.CTkLabel(inf, text=det, text_color="#CBD5E1", justify="left", font=("Inter", 14)).pack(anchor="w", pady=(10,0))
            
            acts = ctk.CTkFrame(c, fg_color="transparent")
            acts.pack(side="right", padx=15, pady=15)
            row1 = ctk.CTkFrame(acts, fg_color="transparent")
            row1.pack(anchor="e", pady=(0, 10))
            if b.get('lat'): ctk.CTkButton(row1, text="🗺️ Map", fg_color="#3B82F6", width=90, command=lambda l1=b['lat'], l2=b['lng']: webbrowser.open(f"https://www.google.com/maps/dir/?api=1&destination={l1},{l2}")).pack(side="left", padx=5)
            ctk.CTkButton(row1, text="💬 WhatsApp", fg_color="#10B981", width=105, command=lambda phone=str(b.get('customer_phone','')).replace(' ','').replace('+',''): webbrowser.open(f"https://wa.me/{phone}")).pack(side="left", padx=5)
            if b.get('status') == 'Pending':
                row2 = ctk.CTkFrame(acts, fg_color="transparent")
                row2.pack(anchor="e")
                ctk.CTkButton(row2, text="🤖 AI Auto-Assign", fg_color="#8B5CF6", width=120, command=lambda bid=b['id'], srv=b['service']: self.auto_assign(bid, srv)).pack(side="left", padx=5)
                ctk.CTkButton(row2, text="✔️ Accept", fg_color="#10B981", width=90, command=lambda bid=b['id']: self.post_action({"action": "update_booking_status", "booking_id": bid, "status": "Accepted"})).pack(side="left", padx=5)
                ctk.CTkButton(row2, text="✖️ Reject", fg_color="#EF4444", width=80, command=lambda bid=b['id']: self.post_action({"action": "update_booking_status", "booking_id": bid, "status": "Rejected"})).pack(side="left", padx=5)

    def render_tickets(self, tickets):
        scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)
        filtered = [t for t in tickets if self.search_query in json.dumps(t).lower()] if self.search_query else tickets
        if not filtered:
            ctk.CTkLabel(scroll, text="No customer support tickets received.", font=("Inter", 16)).pack(pady=40)
            return

        for t in filtered:
            c = ctk.CTkFrame(scroll, corner_radius=12, fg_color="#1E293B", border_width=1, border_color="#D97706")
            c.pack(fill="x", padx=10, pady=8)
            
            # Left Info
            inf = ctk.CTkFrame(c, fg_color="transparent")
            inf.pack(side="left", fill="both", expand=True, padx=20, pady=15)
            
            ctk.CTkLabel(inf, text=f"🎫 {t.get('id', 'TKT')} - From: {t.get('customer', 'User')} ({t.get('date', '')})", font=ctk.CTkFont(size=16, weight="bold"), text_color="#F59E0B").pack(anchor="w")

            details = []
            if t.get('phone'): details.append(f"📞 {t.get('phone')}")
            if t.get('email'): details.append(f"✉️ {t.get('email')}")
            if t.get('address'): details.append(f"📍 {t.get('address')}")
            if details:
                ctk.CTkLabel(inf, text="  |  ".join(details), text_color="#CBD5E1", font=("Inter", 13)).pack(anchor="w", pady=(2, 8))

            ctk.CTkLabel(inf, text=f"Customer MSG: \"{t.get('message', '')}\"", text_color="white", font=("Inter", 15, "italic")).pack(anchor="w", pady=(10,5))
            
            admin_re = t.get('admin_reply', '')
            bot_re = t.get('reply', '')
            if admin_re:
                ctk.CTkLabel(inf, text=f"✅ Sent by Admin: \"{admin_re}\"", text_color="#10B981", font=("Inter", 14)).pack(anchor="w")
            elif bot_re:
                ctk.CTkLabel(inf, text=f"🤖 Bot Auto-Reply: \"{bot_re}\"", text_color="#A78BFA", font=("Inter", 14)).pack(anchor="w")

            # Right Reply Action
            acts = ctk.CTkFrame(c, fg_color="transparent")
            acts.pack(side="right", padx=15, pady=15)
            
            reply_ent = ctk.CTkEntry(acts, placeholder_text="Type reply to customer...", width=250)
            reply_ent.pack(side="left", padx=10)
            ctk.CTkButton(acts, text="📤 Send to Customer", fg_color="#10B981", hover_color="#059669", font=("Inter", 13, "bold"),
                          command=lambda tid=t['id'], e=reply_ent: self.send_admin_reply(tid, e.get())).pack(side="left")

    def send_admin_reply(self, ticket_id, msg):
        if not msg.strip():
            self.show_toast("Please type a reply message first!")
            return
        def _send():
            try:
                # Post to CLOUD server using new unified endpoint
                requests.post(f"{self.CLOUD}/api/admin/reply",
                    json={"ticket_id": ticket_id, "reply": msg}, timeout=15)
            except: pass
            try:
                requests.post("http://127.0.0.1:5000/api/admin/reply",
                    json={"ticket_id": ticket_id, "reply": msg}, timeout=5)
            except: pass
            # Also update local backup file
            local_ticket_path = "support_local.json"
            try:
                with open(local_ticket_path, 'r', encoding='utf-8') as f:
                    tickets = json.load(f)
                for t in tickets:
                    if t.get('id') == ticket_id:
                        t['admin_reply'] = msg
                        t['status'] = 'Replied'
                        break
                with open(local_ticket_path, 'w', encoding='utf-8') as f:
                    json.dump(tickets, f, indent=2)
            except: pass
            self.last_data_hash = ""
            self.after(0, lambda: self.show_toast("✅ Reply sent to customer!"))
            self.after(500, self.get_data_bg)
        threading.Thread(target=_send, daemon=True).start()

    def send_chat_reply(self, msg_index, msg):
        """Send admin reply to a chatbot message by index"""
        if not msg.strip():
            self.show_toast("Please type a reply first!")
            return
        def _send():
            try:
                requests.post(f"{self.CLOUD}/api/admin/reply",
                    json={"index": msg_index, "reply": msg}, timeout=15)
            except: pass
            try:
                requests.post("http://127.0.0.1:5000/api/admin/reply",
                    json={"index": msg_index, "reply": msg}, timeout=5)
            except: pass
            self.last_data_hash = ""
            self.after(0, lambda: self.show_toast("💬 Reply sent to user!"))
            self.after(500, self.get_data_bg)
        threading.Thread(target=_send, daemon=True).start()

    def render_chat(self, chat_messages):
        """Render Live Chat Support tab — shows chatbot conversation history"""
        scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)
        filtered = [m for m in chat_messages if self.search_query in json.dumps(m).lower()] if self.search_query else chat_messages
        if not filtered:
            ctk.CTkLabel(scroll, text="No chatbot messages received yet.", font=("Inter", 16), text_color="#9CA3AF").pack(pady=40)
            return

        for i, msg in enumerate(reversed(filtered)):
            real_index = len(chat_messages) - 1 - i
            has_admin_reply = msg.get('admin_reply', '') != ''
            border_col = "#10B981" if has_admin_reply else "#06B6D4"
            c = ctk.CTkFrame(scroll, corner_radius=12, fg_color="#1E293B", border_width=1, border_color=border_col)
            c.pack(fill="x", padx=10, pady=8)

            inf = ctk.CTkFrame(c, fg_color="transparent")
            inf.pack(side="left", fill="both", expand=True, padx=20, pady=15)

            ctk.CTkLabel(inf, text=f"👤 User ID: {msg.get('user_id', 'Unknown')}   |   🕒 {msg.get('time', '')[:19]}",
                         font=ctk.CTkFont(size=14, weight="bold"), text_color="#06B6D4").pack(anchor="w")
            ctk.CTkLabel(inf, text=f"💬 User: \"{msg.get('user_message', '')}\"",
                         font=("Inter", 14), text_color="white").pack(anchor="w", pady=(8, 2))
            ctk.CTkLabel(inf, text=f"🤖 Bot: \"{msg.get('bot_reply', '')}\"",
                         font=("Inter", 13, "italic"), text_color="#A78BFA").pack(anchor="w", pady=(2, 8))

            if has_admin_reply:
                ctk.CTkLabel(inf, text=f"✅ Admin Reply: \"{msg.get('admin_reply')}\"",
                             font=("Inter", 13, "bold"), text_color="#10B981").pack(anchor="w")
            else:
                acts = ctk.CTkFrame(c, fg_color="transparent")
                acts.pack(side="right", padx=15, pady=15)
                reply_ent = ctk.CTkEntry(acts, placeholder_text="Type reply to user...", width=250)
                reply_ent.pack(side="left", padx=10)
                ctk.CTkButton(acts, text="📤 Send Reply", fg_color="#10B981", hover_color="#059669",
                              font=("Inter", 13, "bold"),
                              command=lambda idx=real_index, e=reply_ent: self.send_chat_reply(idx, e.get())).pack(side="left")


    def render_workers(self, workers_dict):
        scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)
        for srv, workers in workers_dict.items():
            filtered = [w for w in workers if self.search_query in json.dumps(w).lower()] if self.search_query else workers
            if not filtered: continue
            ctk.CTkLabel(scroll, text=f"⚡ {srv.upper()} ({len(filtered)})", font=ctk.CTkFont(size=18, weight="bold"), text_color="#A78BFA").pack(anchor="w", padx=10, pady=(20, 10))
            for w in filtered:
                c = ctk.CTkFrame(scroll, corner_radius=12, fg_color="#1E293B", border_width=1, border_color="#334155")
                c.pack(fill="x", padx=10, pady=8)
                inf = ctk.CTkFrame(c, fg_color="transparent"); inf.pack(side="left", fill="both", expand=True, padx=20, pady=15)
                status_clr = "#10B981" if w.get('isOnline') else "#6B7280"
                ctk.CTkLabel(inf, text=f"{w['name']}", font=ctk.CTkFont(size=18, weight="bold"), text_color="white").pack(side="left")
                pill = ctk.CTkFrame(inf, fg_color=status_clr, corner_radius=10, height=24, width=80); pill.pack(side="left", padx=15); pill.pack_propagate(False)
                ctk.CTkLabel(pill, text="Online" if w.get('isOnline') else "Offline", text_color="white", font=("Inter", 12, "bold")).place(relx=0.5, rely=0.5, anchor="center")
                ctk.CTkLabel(inf, text=f"📞 {w['phone']}   |   📍 {w.get('location','Local')}   |   📈 Jobs: {w.get('jobsDone', 0)}", text_color="#CBD5E1", font=("Inter", 14)).pack(side="left", padx=10)
                acts = ctk.CTkFrame(c, fg_color="transparent"); acts.pack(side="right", padx=15)
                ctk.CTkButton(acts, text="⚙️ Modify", fg_color="#F59E0B", text_color="black", width=90, font=("Inter", 13, "bold"), command=lambda s=srv, wid=w['id'], worker=w: self.open_edit(s, wid, worker)).pack(side="left", padx=5)
                ctk.CTkButton(acts, text="🔌 Status", fg_color="#3B82F6", width=90, font=("Inter", 13, "bold"), command=lambda wid=w['id']: [requests.post("http://127.0.0.1:5000/api/toggle_worker", json={"worker_id": wid}), setattr(self, 'last_data_hash', ''), self.get_data_bg()]).pack(side="left", padx=5)
                ctk.CTkButton(acts, text="🗑️", fg_color="transparent", text_color="#EF4444", border_width=1, border_color="#EF4444", width=40, command=lambda s=srv, wid=w['id']: self.post_action({"action": "delete", "service": s, "worker_id": wid})).pack(side="left", padx=5)

    def render_system(self):
        f = ctk.CTkFrame(self.content_frame, fg_color="#1E293B", corner_radius=15)
        f.pack(fill="both", expand=True, padx=40, pady=30)
        ctk.CTkLabel(f, text="💾 Database & Data Management", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(40, 20))
        ctk.CTkLabel(f, text="Create instant snapshots of your current databases.", font=("Inter", 14), text_color="#9CA3AF").pack(pady=10)
        ctk.CTkButton(f, text="🛡️ Perform Instant Backup", font=("Inter", 16, "bold"), fg_color="#8B5CF6", height=50, width=400, command=self.do_backup).pack(pady=40)

    def do_backup(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("backups", exist_ok=True)
        try:
            if os.path.exists("database.json"): shutil.copy("database.json", f"backups/database_{ts}.json")
            if os.path.exists("bookings.json"): shutil.copy("bookings.json", f"backups/bookings_{ts}.json")
            self.show_toast("🛡️ Successfully Backed Up Data!")
        except Exception as e: self.show_toast(f"Error: {e}")

    def export_csv(self):
        bookings = self.bookings_cache
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], initialfile="fixmate_bookings.csv", title="Export Bookings")
        if filepath:
            with open(filepath, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['ID','Date','Customer','Phone','Address','Worker','Service','Booking Date','Time','Status','Note'])
                for b in bookings: writer.writerow([b.get('id',''), b.get('date_created',''), b.get('customer_name',''), b.get('customer_phone',''), b.get('customer_address',''), b.get('worker_name',''), b.get('service',''), b.get('date',''), b.get('time',''), b.get('status',''), b.get('note','')])
            self.show_toast("CSV Exported Successfully!")

    def open_add_worker(self):
        t = ctk.CTkToplevel(self); t.title("Add New Worker"); t.geometry("400x550"); t.attributes("-topmost", True)
        ctk.CTkLabel(t, text="➕ Add FixMate Worker", font=ctk.CTkFont(weight="bold", size=22), text_color="#A78BFA").pack(pady=(20, 10))
        srv_combo = ctk.CTkComboBox(t, values=["electrician", "plumber", "cleaner", "carpenter", "mechanic", "painter", "medical", "grocery"], width=320); srv_combo.pack(pady=5)
        name_entry = ctk.CTkEntry(t, width=320, placeholder_text="Name"); name_entry.pack(pady=5)
        phone_entry = ctk.CTkEntry(t, width=320, placeholder_text="Phone"); phone_entry.pack(pady=5)
        loc_entry = ctk.CTkEntry(t, width=320, placeholder_text="City"); loc_entry.pack(pady=5)
        def save():
            self.post_action({"action": "add", "service": srv_combo.get(), "name": name_entry.get(), "phone": phone_entry.get(), "location": loc_entry.get(), "experience": "1 year", "is_online": "on", "rating": "5.0"})
            t.destroy(); self.switch_view("workers")
        ctk.CTkButton(t, text="✔️ Save", fg_color="#10B981", height=45, width=320, command=save).pack(pady=30)

    def open_edit(self, srv, wid, worker_data):
        t = ctk.CTkToplevel(self); t.title(f"Edit"); t.geometry("400x400"); t.attributes("-topmost", True)
        name_entry = ctk.CTkEntry(t, width=320); name_entry.insert(0, worker_data['name']); name_entry.pack(pady=10)
        phone_entry = ctk.CTkEntry(t, width=320); phone_entry.insert(0, worker_data['phone']); phone_entry.pack(pady=10)
        loc_entry = ctk.CTkEntry(t, width=320); loc_entry.insert(0, worker_data.get('location', '')); loc_entry.pack(pady=10)
        def save():
            self.post_action({"action": "edit", "service": srv, "worker_id": wid, "name": name_entry.get(), "phone": phone_entry.get(), "location": loc_entry.get(), "is_online": "on" if worker_data.get('isOnline') else ""})
            t.destroy()
        ctk.CTkButton(t, text="✔️ Update", fg_color="#3B82F6", height=45, width=320, command=save).pack(pady=30)

if __name__ == "__main__":
    t = threading.Thread(target=start_server); t.daemon = True; t.start(); time.sleep(1.5)
    app = FixMateApp(); app.mainloop()
