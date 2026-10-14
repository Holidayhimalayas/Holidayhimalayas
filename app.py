import streamlit as st
import pandas as pd
from datetime import datetime, date
from sqlalchemy import create_engine, text

# Page Configuration
st.set_page_config(page_title="Accounts", page_icon="📊", layout="wide")

# Database Connection via Secrets or fallback
db_url = st.secrets.get("DATABASE_URL", None)

if not db_url:
    st.error("⚠️ Database connection URL not found! Please set DATABASE_URL in Streamlit Secrets.")
    st.stop()

# Fix URI scheme if needed (PostgreSQL requirement)
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url, pool_pre_ping=True)

def init_db():
    with engine.begin() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS bookings (
                id SERIAL PRIMARY KEY,
                customer_name TEXT,
                trip_name TEXT,
                total_amount REAL,
                hotel_cost REAL,
                transport_cost REAL,
                other_costs REAL,
                created_date TEXT
            );
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                date TEXT,
                tx_type TEXT,
                party_name TEXT,
                category TEXT,
                amount REAL,
                payment_method TEXT,
                notes TEXT,
                booking_id INTEGER
            );
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS ledger (
                id SERIAL PRIMARY KEY,
                date TEXT,
                account_name TEXT,
                debit REAL,
                credit REAL,
                narration TEXT
            );
        '''))

init_db()

# Initialize session state navigation
if "nav" not in st.session_state:
    st.session_state.nav = "Home (Dashboard)"

# Display Logo in Sidebar
try:
    st.sidebar.image("logo.png", use_container_width=True)
except Exception:
    st.sidebar.info("Upload 'logo.png' to GitHub to display your logo here.")

st.sidebar.title("Navigation")
nav_options = [
    "Home (Dashboard)", 
    "New Booking", 
    "Money Received", 
    "Money Paid", 
    "Add an Expense", 
    "View My Business", 
    "Ask Assistant", 
    "Accountant & Advanced Reports"
]

# Safe navigation sync
current_index = nav_options.index(st.session_state.nav) if st.session_state.nav in nav_options else 0
selected_action = st.sidebar.radio("Select Action", nav_options, index=current_index)

if selected_action != st.session_state.nav:
    st.session_state.nav = selected_action
    st.rerun()

def run_query(query_str, params={}):
    with engine.connect() as conn:
        return pd.read_sql_query(text(query_str), conn, params=params)

def execute_db(query_str, params={}):
    with engine.begin() as conn:
        conn.execute(text(query_str), params)

# --- HOME / DASHBOARD ---
if st.session_state.nav == "Home (Dashboard)":
    st.title("Accounts")
    st.write("A simplified accounting tool for your business.")
    
    bookings_df = run_query("SELECT * FROM bookings")
    tx_df = run_query("SELECT * FROM transactions")
    
    total_bookings = len(bookings_df)
    total_sales = bookings_df['total_amount'].sum() if not bookings_df.empty else 0.0
    
    received_df = tx_df[tx_df['tx_type'] == 'Money Received'] if not tx_df.empty else pd.DataFrame()
    total_received = received_df['amount'].sum() if not received_df.empty else 0.0
    
    paid_df = tx_df[tx_df['tx_type'].isin(['Money Paid', 'Expense'])] if not tx_df.empty else pd.DataFrame()
    total_paid = paid_df['amount'].sum() if not paid_df.empty else 0.0
    
    money_available = total_received - total_paid
    customers_owe = total_sales - total_received
    
    total_costs = 0.0
    if not bookings_df.empty:
        total_costs = (bookings_df['hotel_cost'] + bookings_df['transport_cost'] + bookings_df['other_costs']).sum()
    estimated_profit = total_sales - total_costs

    st.subheader("Your business at a glance.")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Money Available in Bank/Cash", f"₹{money_available:,.0f}")
    col2.metric("📥 Money Received (Total)", f"₹{total_received:,.0f}")
    col3.metric("📈 Estimated Business Profit", f"₹{estimated_profit:,.0f}")

    col4, col5, col6 = st.columns(3)
    col4.metric("👥 Customers Still Owe Us", f"₹{customers_owe:,.0f}")
    col5.metric("💸 Money Paid Out", f"₹{total_paid:,.0f}")
    col6.metric("📋 Total Active Bookings", f"{total_bookings}")

    st.markdown("---")
    st.subheader("🚀 Quick Action Hub")
    
    b1, b2, b3, b4, b5 = st.columns(5)
    with b1:
        if st.button("📋 New Booking", use_container_width=True):
            st.session_state.nav = "New Booking"
            st.rerun()
    with b2:
        if st.button("📥 Money Received", use_container_width=True):
            st.session_state.nav = "Money Received"
            st.rerun()
    with b3:
        if st.button("💸 Money Paid", use_container_width=True):
            st.session_state.nav = "Money Paid"
            st.rerun()
    with b4:
        if st.button("🧾 Add Expense", use_container_width=True):
            st.session_state.nav = "Add an Expense"
            st.rerun()
    with b5:
        if st.button("📊 View Business", use_container_width=True):
            st.session_state.nav = "View My Business"
            st.rerun()

# --- NEW BOOKING ---
elif st.session_state.nav == "New Booking":
    st.title("📋 Create New Booking / Trip")
    with st.form("booking_form"):
        tx_date = st.date_input("Booking Date", value=date.today())
        customer_name = st.text_input("Customer Name")
        trip_name = st.text_input("Trip Name (e.g. Spiti Valley Circuit)")
        total_amount = st.number_input("Total Booking Amount (Sales in ₹)", min_value=0.0, step=1000.0)
        hotel_cost = st.number_input("Expected Hotel Cost (₹)", min_value=0.0, step=500.0)
        transport_cost = st.number_input("Expected Transport Cost (₹)", min_value=0.0, step=500.0)
        other_costs = st.number_input("Other Expected Direct Costs (₹)", min_value=0.0, step=500.0)
        
        submitted = st.form_submit_button("Save Booking")
        if submitted:
            if customer_name and trip_name:
                date_str = tx_date.strftime("%Y-%m-%d")
                execute_db(
                    "INSERT INTO bookings (customer_name, trip_name, total_amount, hotel_cost, transport_cost, other_costs, created_date) VALUES (:cn, :tn, :ta, :hc, :tc, :oc, :cd)",
                    {"cn": customer_name, "tn": trip_name, "ta": total_amount, "hc": hotel_cost, "tc": transport_cost, "oc": other_costs, "cd": date_str}
                )
                execute_db(
                    "INSERT INTO ledger (date, account_name, debit, credit, narration) VALUES (:d, :an, :deb, :cred, :narr)",
                    {"d": date_str, "an": "Customer Receivables", "deb": total_amount, "cred": 0, "narr": f"Booking #{trip_name} for {customer_name}"}
                )
                execute_db(
                    "INSERT INTO ledger (date, account_name, debit, credit, narration) VALUES (:d, :an, :deb, :cred, :narr)",
                    {"d": date_str, "an": "Sales Revenue", "deb": 0, "cred": total_amount, "narr": f"Revenue from {customer_name}"}
                )
                st.success(f"Booking for {customer_name} successfully saved!")
            else:
                st.error("Please fill in both Customer Name and Trip Name.")

# --- MONEY RECEIVED ---
elif st.session_state.nav == "Money Received":
    st.title("📥 Record Money Received from Customer")
    bookings_df = run_query("SELECT id, customer_name, trip_name FROM bookings")
    
    if bookings_df.empty:
        st.warning("No bookings found. Please create a booking first!")
    else:
        booking_options = {f"Trip #{row['id']}: {row['trip_name']} - {row['customer_name']}": row['id'] for _, row in bookings_df.iterrows()}
        
        with st.form("received_form"):
            tx_date = st.date_input("Payment Received Date", value=date.today())
            selected_booking_label = st.selectbox("Select Booking", list(booking_options.keys()))
            booking_id = int(booking_options[selected_booking_label])
            
            amount = st.number_input("Amount Received (₹)", min_value=0.0, step=500.0)
            payment_method = st.selectbox("Payment Method", ["UPI", "Bank Transfer (NEFT/IMPS/UPI)", "Cash", "Credit Card"])
            notes = st.text_input("Notes / Reference Number")
            
            submitted = st.form_submit_button("Save Payment Received")
            if submitted:
                date_str = tx_date.strftime("%Y-%m-%d")
                selected_row = bookings_df[bookings_df['id'] == booking_id].iloc[0]
                party_name = selected_row['customer_name']
                
                execute_db(
                    "INSERT INTO transactions (date, tx_type, party_name, category, amount, payment_method, notes, booking_id) VALUES (:d, :txt, :pn, :cat, :amt, :pm, :notes, :bid)",
                    {"d": date_str, "txt": "Money Received", "pn": party_name, "cat": "Customer Advance/Payment", "amt": amount, "pm": payment_method, "notes": notes, "bid": booking_id}
                )
                execute_db(
                    "INSERT INTO ledger (date, account_name, debit, credit, narration) VALUES (:d, :an, :deb, :cred, :narr)",
                    {"d": date_str, "an": "Bank/Cash Account", "deb": amount, "cred": 0, "narr": f"Received from {party_name}"}
                )
                execute_db(
                    "INSERT INTO ledger (date, account_name, debit, credit, narration) VALUES (:d, :an, :deb, :cred, :narr)",
                    {"d": date_str, "an": "Customer Receivables", "deb": 0, "cred": amount, "narr": f"Payment recorded for booking #{booking_id}"}
                )
                st.success("Payment recorded successfully!")

# --- MONEY PAID ---
elif st.session_state.nav == "Money Paid":
    st.title("💸 Record Money Paid / Supplier Payment")
    bookings_df = run_query("SELECT id, customer_name, trip_name FROM bookings")
    
    with st.form("paid_form"):
        tx_date = st.date_input("Payment Out Date", value=date.today())
        booking_id = None
        if not bookings_df.empty:
            booking_options = {"None / General Business Expense": None}
            for _, row in bookings_df.iterrows():
                booking_options[f"Trip #{row['id']}: {row['trip_name']} - {row['customer_name']}"] = row['id']
            selected_booking_label = st.selectbox("Link to Customer Booking / Trip", list(booking_options.keys()))
            booking_id = booking_options[selected_booking_label]
            if booking_id is not None:
                booking_id = int(booking_id)
        
        party_name = st.text_input("Supplier / Payee Name (e.g. Sukh Sagar Regency, Transport Provider)")
        category = st.selectbox("Expense Category", ["Hotel Booking", "Transport / Cab", "Guide / Permits", "Food / Meals", "Other Direct Cost", "Office / Overhead Expense"])
        amount = st.number_input("Amount Paid (₹)", min_value=0.0, step=500.0)
        payment_method = st.selectbox("Payment Method", ["Bank Transfer", "UPI", "Cash", "Credit Card"])
        notes = st.text_input("Notes / Invoice Number")
        
        submitted = st.form_submit_button("Save Payment Out")
        if submitted:
            if party_name and amount > 0:
                date_str = tx_date.strftime("%Y-%m-%d")
                
                execute_db(
                    "INSERT INTO transactions (date, tx_type, party_name, category, amount, payment_method, notes, booking_id) VALUES (:d, :txt, :pn, :cat, :amt, :pm, :notes, :bid)",
                    {"d": date_str, "txt": "Money Paid", "pn": party_name, "cat": category, "amt": amount, "pm": payment_method, "notes": notes, "bid": booking_id}
                )
                execute_db(
                    "INSERT INTO ledger (date, account_name, debit, credit, narration) VALUES (:d, :an, :deb, :cred, :narr)",
                    {"d": date_str, "an": "Business Expenses / Suppliers", "deb": amount, "cred": 0, "narr": f"{category} paid to {party_name}"}
                )
                execute_db(
                    "INSERT INTO ledger (date, account_name, debit, credit, narration) VALUES (:d, :an, :deb, :cred, :narr)",
                    {"d": date_str, "an": "Bank/Cash Account", "deb": 0, "cred": amount, "narr": f"Paid ₹{amount} via {payment_method}"}
                )
                st.success("Supplier payment recorded successfully!")
            else:
                st.error("Please enter a valid Payee Name and Amount.")

# --- ADD AN EXPENSE ---
elif st.session_state.nav == "Add an Expense":
    st.title("🧾 Add Trip Expense")
    bookings_df = run_query("SELECT id, customer_name, trip_name FROM bookings")
    with st.form("expense_form"):
        tx_date = st.date_input("Expense Date", value=date.today())
        booking_id = None
        if not bookings_df.empty:
            booking_options = {"None / General Business Expense": None}
            for _, row in bookings_df.iterrows():
                booking_options[f"Trip #{row['id']}: {row['trip_name']} - {row['customer_name']}"] = row['id']
            selected_booking_label = st.selectbox("Link to Customer Booking / Trip", list(booking_options.keys()))
            booking_id = booking_options[selected_booking_label]
            if booking_id is not None:
                booking_id = int(booking_id)
        
        party_name = st.text_input("Vendor / Expense Party Name")
        category = st.selectbox("Category", ["Hotel Booking", "Transport / Cab", "Guide / Permits", "Food / Meals", "Other Direct Cost"])
        amount = st.number_input("Expense Amount (₹)", min_value=0.0, step=500.0)
        payment_method = st.selectbox("Payment Method", ["Bank Transfer", "UPI", "Cash"])
        notes = st.text_input("Notes")
        
        if st.form_submit_button("Save Expense"):
            if party_name and amount > 0:
                date_str = tx_date.strftime("%Y-%m-%d")
                execute_db(
                    "INSERT INTO transactions (date, tx_type, party_name, category, amount, payment_method, notes, booking_id) VALUES (:d, :txt, :pn, :cat, :amt, :pm, :notes, :bid)",
                    {"d": date_str, "txt": "Expense", "pn": party_name, "cat": category, "amt": amount, "pm": payment_method, "notes": notes, "bid": booking_id}
                )
                execute_db(
                    "INSERT INTO ledger (date, account_name, debit, credit, narration) VALUES (:d, :an, :deb, :cred, :narr)",
                    {"d": date_str, "an": "Business Expenses / Suppliers", "deb": amount, "cred": 0, "narr": f"Expense: {category} - {party_name}"}
                )
                execute_db(
                    "INSERT INTO ledger (date, account_name, debit, credit, narration) VALUES (:d, :an, :deb, :cred, :narr)",
                    {"d": date_str, "an": "Bank/Cash Account", "deb": 0, "cred": amount, "narr": f"Paid {amount} for {category}"}
                )
                st.success("Expense saved successfully!")

# --- VIEW MY BUSINESS ---
elif st.session_state.nav == "View My Business":
    st.title("📊 Business Overview & Booking Summaries")
    tab1, tab2, tab3, tab4 = st.tabs(["Bookings Financial Summary", "Money Tracker", "Recent Transactions", "🗑️ Delete an Entry"])
    
    with tab1:
        st.subheader("Booking Financial Breakdowns")
        bookings_df = run_query("SELECT * FROM bookings")
        tx_df = run_query("SELECT * FROM transactions")
        
        if bookings_df.empty:
            st.info("No bookings recorded yet.")
        else:
            for _, row in bookings_df.iterrows():
                b_id = row['id']
                cust = row['customer_name']
                trip = row['trip_name']
                total_amt = row['total_amount']
                hotel = row['hotel_cost']
                transport = row['transport_cost']
                other = row['other_costs']
                
                b_tx = tx_df[(tx_df['booking_id'] == b_id) & (tx_df['tx_type'] == 'Money Received')] if not tx_df.empty else pd.DataFrame()
                received = b_tx['amount'].sum() if not b_tx.empty else 0.0
                still_to_collect = total_amt - received
                
                est_profit = total_amt - (hotel + transport + other)
                
                with st.expander(f"Trip #{b_id}: {trip} — Customer: {cust}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**Customer Booking Amount:** ₹{total_amt:,.0f}")
                        st.write(f"**Money Received:** ₹{received:,.0f}")
                        st.write(f"**Money Still to Collect:** ₹{still_to_collect:,.0f}")
                    with c2:
                        st.write(f"**Hotel Cost:** ₹{hotel:,.0f}")
                        st.write(f"**Transport Cost:** ₹{transport:,.0f}")
                        st.write(f"**Other Direct Costs:** ₹{other:,.0f}")
                    st.markdown(f"🟢 **Estimated Booking Profit:** ₹{est_profit:,.0f} *(before taxes and allocated overheads)*")

    with tab2:
        st.subheader("Money Tracker & Cash Flow")
        tx_df = run_query("SELECT * FROM transactions")
        if not tx_df.empty:
            st.dataframe(tx_df)
        else:
            st.info("No transactions recorded yet.")

    with tab3:
        st.subheader("Complete Transaction History")
        tx_df = run_query("SELECT date, tx_type, party_name, category, amount, payment_method, notes, booking_id FROM transactions")
        if not tx_df.empty:
            st.dataframe(tx_df)
        else:
            st.info("No transaction history found.")

    with tab4:
        st.subheader("🗑️ Delete Incorrect or Canceled Entries")
        st.write("Permanently remove an entry if you made a mistake or a customer canceled.")
        
        delete_type = st.radio("What would you like to delete?", ["A Booking", "A Transaction / Payment", "A Ledger Record"], horizontal=True)
        
        if delete_type == "A Booking":
            bookings_df = run_query("SELECT id, customer_name, trip_name, total_amount FROM bookings")
            if bookings_df.empty:
                st.info("No bookings available to delete.")
            else:
                b_map = {f"ID #{r['id']} | {r['customer_name']} - {r['trip_name']} (₹{r['total_amount']:,.0f})": int(r['id']) for _, r in bookings_df.iterrows()}
                selected_label = st.selectbox("Select Booking to Delete", list(b_map.keys()))
                del_id = b_map[selected_label]
                
                if st.button("🔴 Permanently Delete Selected Booking", type="primary"):
                    execute_db("DELETE FROM bookings WHERE id = :id", {"id": del_id})
                    st.success(f"Booking #{del_id} deleted successfully!")
                    st.rerun()

        elif delete_type == "A Transaction / Payment":
            tx_df = run_query("SELECT id, date, tx_type, party_name, amount FROM transactions")
            if tx_df.empty:
                st.info("No transactions available to delete.")
            else:
                t_map = {f"ID #{r['id']} | {r['date']} | {r['tx_type']} | {r['party_name']} - ₹{r['amount']:,.0f}": int(r['id']) for _, r in tx_df.iterrows()}
                selected_label = st.selectbox("Select Transaction to Delete", list(t_map.keys()))
                del_id = t_map[selected_label]
                
                if st.button("🔴 Permanently Delete Selected Transaction", type="primary"):
                    execute_db("DELETE FROM transactions WHERE id = :id", {"id": del_id})
                    st.success(f"Transaction #{del_id} deleted successfully!")
                    st.rerun()

        elif delete_type == "A Ledger Record":
            ledger_df = run_query("SELECT id, date, account_name, debit, credit, narration FROM ledger")
            if ledger_df.empty:
                st.info("No ledger entries available to delete.")
            else:
                l_map = {f"ID #{r['id']} | {r['date']} | {r['account_name']} | {r['narration']}": int(r['id']) for _, r in ledger_df.iterrows()}
                selected_label = st.selectbox("Select Ledger Entry to Delete", list(l_map.keys()))
                del_id = l_map[selected_label]
                
                if st.button("🔴 Permanently Delete Selected Ledger Record", type="primary"):
                    execute_db("DELETE FROM ledger WHERE id = :id", {"id": del_id})
                    st.success(f"Ledger record #{del_id} deleted successfully!")
                    st.rerun()

# --- ASK ASSISTANT ---
elif st.session_state.nav == "Ask Assistant":
    st.title("🤖 Ask Business Assistant")
    st.write("Ask any question about your bookings, customer balances, cash flow, or profits!")
    user_q = st.text_input("Type your question here (e.g., How much does Dinesh owe?)")
    
    if user_q:
        q_lower = user_q.lower()
        bookings_df = run_query("SELECT * FROM bookings")
        tx_df = run_query("SELECT * FROM transactions")
        
        found_response = False
        
        if not bookings_df.empty:
            for _, row in bookings_df.iterrows():
                cust_name = str(row['customer_name'])
                if cust_name.lower() in q_lower or any(part.lower() in q_lower for part in cust_name.split()):
                    b_id = row['id']
                    total_amt = row['total_amount']
                    trip = row['trip_name']
                    
                    b_tx = tx_df[(tx_df['booking_id'] == b_id) & (tx_df['tx_type'] == 'Money Received')] if not tx_df.empty else pd.DataFrame()
                    received = b_tx['amount'].sum() if not b_tx.empty else 0.0
                    owed = total_amt - received
                    
                    st.success(f"📌 **{cust_name}** ({trip}):")
                    st.write(f"- Total Booking Amount: **₹{total_amt:,.0f}**")
                    st.write(f"- Received So Far: **₹{received:,.0f}**")
                    st.write(f"- **Balance Still Owed: ₹{owed:,.0f}**")
                    found_response = True
                    break
        
        if not found_response:
            if "profit" in q_lower:
                total_sales = bookings_df['total_amount'].sum() if not bookings_df.empty else 0.0
                total_costs = (bookings_df['hotel_cost'] + bookings_df['transport_cost'] + bookings_df['other_costs']).sum() if not bookings_df.empty else 0.0
                st.info(f"📈 **Estimated Profit:** ₹{total_sales - total_costs:,.0f} (Revenue: ₹{total_sales:,.0f} − Costs: ₹{total_costs:,.0f})")
            elif "owe" in q_lower or "due" in q_lower or "balance" in q_lower:
                total_sales = bookings_df['total_amount'].sum() if not bookings_df.empty else 0.0
                received_df = tx_df[tx_df['tx_type'] == 'Money Received'] if not tx_df.empty else pd.DataFrame()
                total_received = received_df['amount'].sum() if not received_df.empty else 0.0
                st.info(f"👥 **Total Balance Owed by All Customers:** ₹{total_sales - total_received:,.0f}")
            else:
                st.info(f"You have **{len(bookings_df)} active booking(s)** in system. Ask about a specific customer (like 'Dinesh' or 'Priti') to view detailed balances!")

# --- ACCOUNTANT & ADVANCED REPORTS ---
elif st.session_state.nav == "Accountant & Advanced Reports":
    st.title("🏛️ Accountant & Advanced Reports Section")
    st.warning("This section contains professional double-entry accounting records, general ledger entries, and tax summaries intended for your Chartered Accountant.")
    
    ledger_df = run_query("SELECT * FROM ledger")
    st.subheader("Professional General Ledger (Double-Entry Log)")
    if not ledger_df.empty:
        st.dataframe(ledger_df)
        csv = ledger_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Accountant Ledger (CSV)", csv, "accountant_ledger.csv", "text/csv")
    else:
        st.info("Ledger is empty.")
