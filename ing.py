#! /usr/bin/python3

import re
import sys
import datetime
import time
import bisect
import json

def itastr2amount(s):
    a=s.replace('.','').split(',')
    ret=100*int(a[0])
    if len(a)==2 and len(a[1])>0:
        rem=int(a[1])
        if len(a[1])==1:
            rem=rem*10

        
        if ret<0:
            ret=ret-int(a[1])
        else:
            ret=ret+int(a[1])

    return ret

def engstr2amount(s):

    # maybe there's a swap function ...
    return itastr2amount((s.replace(',','')).replace('.',','))
    
def line_split(line):
    a=(line[1:-2]).split('","')
    return a[0:4]+[a[4][2:]]

class LineError(Exception):
    def __init__(self, arg, info):
        self.args = arg
        self.info = info

class LineSyntaxError(Exception):
    def __init__(self, arg):
        self.args = arg



def process_line(a):

    reason_char='\'\\(\\)A-Za-z0-9 .,-'
    
    information={}
    information["date1"]=datetime.date(int(a[0][6:]),int(a[0][3:5]),int(a[0][0:2]))
    information["date2"]=datetime.date(int(a[1][6:]),int(a[1][3:5]),int(a[1][0:2]))
    information["amount"]=itastr2amount(a[4])
    
    method=a[2]

    try:

        if method=="PAGAMENTO CARTA":
            time_info=re.search(" alle ore ([0-9]+):([0-9]+)",a[3])
            information["time"]=datetime.time(int(time_info[1]),int(time_info[2]))
            information["currency"]=re.search(" Div=([A-Z]+) ",a[3])[1]
            information["amount_currency"]=-engstr2amount(re.search(" Importo in divisa=([0-9.,]+) ",a[3])[1])
            if re.search(" - Transazione C-less$",a[3]):
                information["contactless"]=1
                information["correspondent_name"]=re.search(" presso ([A-Za-z0-9. ]+) - Transazione C-less$",a[3])[1]
            else:
                information["correspondent_name"]=re.search(" presso ([A-Za-z0-9. ]+)",a[3])[1]

            information["method"]="card"

        elif method=="PRELIEVO CARTA":
            time_info=re.search(" alle ore ([0-9]+):([0-9]+)",a[3])
            information["time"]=datetime.time(int(time_info[1]),int(time_info[2]))
            information["currency"]=re.search(" Div=([A-Z]+) ",a[3])[1]
            information["amount_currency"]=-engstr2amount(re.search(" Importo in divisa=([0-9.,]+) ",a[3])[1])
            information["place"]=re.search(" presso ([A-Za-z0-9. ]+)",a[3])[1]

            information["method"]="cash_withdrawal"
    
        elif method=="ACCR. STIPENDIO-PENSIONE":
            information["transaction_id"]=re.search("Bonifico N\\. ([A-Za-z0-9]+)",a[3])[1]
            information["correspondent_id"]=re.search("Codifica Ordinante ([A-Z0-9]+)",a[3])[1]
            information["correspondent_name"]=re.search("Anagrafica Ordinante ([A-Za-z0-9. ]+) Note:",a[3])[1]
            information["reason"]=re.search("Note: (["+reason_char+"]+)$",a[3])[1]

            information["method"]="wage"

        elif method=="ACCREDITO BONIFICO":
            information["transaction_id"]=re.search("Bonifico N\\. ([A-Za-z0-9]+)",a[3])[1]
            information["correspondent_id"]=re.search("Codifica Ordinante ([A-Z0-9]+)",a[3])[1]
            information["correspondent_name"]=re.search("Anagrafica Ordinante ([A-Za-z0-9. ]+) Note:",a[3])[1]
            information["reason"]=re.search("Note: (["+reason_char+"]+)$",a[3])[1]
                
            information["method"]="incoming_transfer"

        elif method=="VS.DISPOSIZIONE":
            if re.search("^BONIFICO DA VOI DISPOSTO NOP",a[3]):
        
                information["transaction_id"]=re.search("^BONIFICO DA VOI DISPOSTO NOP ([A-Za-z0-9]+)",a[3])[1]
                information["correspondent_id"]=re.search(" A FAVORE DI ([A-Za-z0-9. ]+) C. BENEF. ([A-Z0-9]+) NOTE:",a[3])[2]
                information["correspondent_name"]=re.search(" A FAVORE DI ([A-Za-z0-9. ]+) C. BENEF. ([A-Z0-9]+) NOTE:",a[3])[1]
                information["reason"]=re.search(" NOTE: (["+reason_char+"]+)$",a[3])[1]
                
                information["method"]="incoming_transfer"
            
            else:
                information["description"]=a[2]+' '+a[3]
                information["method"]="other"
                raise LineError(a,information)

        elif method=="PAGAMENTI DIVERSI":
            if re.search("Addebito SDD CORE",a[3]):
            
                information["correspondent_id"]=re.search("Creditor id\\. ([A-Z0-9]+)",a[3])[1]
                information["correspondent_name"]=re.search("Creditor id\\. ([A-Z0-9]+) (["+reason_char+"]+) Id Mandato ",a[3])[2]
                tr=re.search(" Rif\\. ([0-9A-Z-]+)$",a[3])
                if tr:
                    information["transaction_id"]=tr[1]
                    information["reason"]=re.search("Id Mandato ([0-9A-Za-z-]+) Debitore",a[3])[1]
            
                information["method"]="sdd"

            else:
                information["description"]=a[2]+' '+a[3]
                information["method"]="other"
                raise LineError(a,information)

        elif method=="BOLLI GOVERNATIVI":
            information["method"]="bolli_governativi"
            information["description"]="bolli_governativi"

        elif method=="Canone servizio SMS OTP":
            information["method"]="sms_otp"
            information["description"]="sms_otp"
            

        else:
            information["description"]=a[2]+' '+a[3]
            information["method"]="other"
            raise LineError(a,information)

    except LineError as e:
        raise 
    except:
        raise LineSyntaxError(a)

        
    return information


def csv2transaction_list(filename):
    f=open(filename)
    f.readline()
    line=f.readline()

    tr=[]
    while line!='' and line!=',,,,\n':
        a=line_split(line)
        info=process_line(a)
        tr.append(info)
        line=f.readline()

    f.close()
    
    return tr



def xls2transaction_list(filename):

# dangerous... potantially a 1TB file may break everithing...
    ff=open(filename)
    f=ff.read()
    ff.close()

    tr=[]
    
    for i in re.findall("""<tr><td border="1">(.+?)</tr>""",f):
        line=re.search("""([0-9/]+)</td><td border="1">([0-9/]+)</td><td border="1">(.+)</td><td border="1">(.+)</td><td class="excelCurrency" border="1">&euro; ([-+0-9,.]+)</td>""",i)
        a=[line[1], line[2], line[3], line[4], line[5]]
        info=process_line(a)
        tr.append(info)
       

    
    return tr




class _jencoder(json.JSONEncoder):
    def default(self, obj):
        dateft="%Y-%m-%d"
        timeft="%H:%M:%S"
        if isinstance(obj, Transactions.Movement):
            data = {  "__Movement__": True,
                      "date_account": obj.date_account,
                      "date_available": obj.date_available,
                      "amount": obj.amount,
                      "method": obj.method,
                      "correspondent_name": obj.correspondent_name,
                      "correspondent_id": obj.correspondent_id,
                      "information": obj.information }
            return data

        if isinstance(obj, Transactions):
            if not obj.initialized:
                return None
            data = { "__Transactions__": True,
                     "start_date": obj.start_date,
                     "end_date": obj.end_date,
                     "account_number": obj.account_number,
                     "iban": obj.iban,
                     "end_account": obj.end_account,
                     "start_account": obj.start_account,
                     "movements": obj.movements }
            return data

        if isinstance(obj,datetime.time):
            return datetime.time.strftime(obj,timeft)

        if isinstance(obj,datetime.date):
            return datetime.date.strftime(obj,dateft)

        return json.JSONEncoder.default(self,obj)






class Transactions:
    def __inif__(self):
        self.initialized=False


    class Movement:
        def __init__(self):
            pass

        def load_xls_line(line):
            l=re.search("""([0-9/]+)</td><td border="1">([0-9/]+)</td><td border="1">(.+)</td><td border="1">(.+)</td><td class="excelCurrency" border="1">&euro; ([-+0-9,.]+)</td>""",line)
            date_account=l[1]
            date_available=l[2]
            method=l[3]
            description=l[4]
            amount_str=l[5]

            reason_char='\'\\(\\)A-Za-z0-9 .,-'

            m=Transactions.Movement()
            
            m.date_account=datetime.date(int(date_account[6:]),int(date_account[3:5]),int(date_account[0:2]))
            m.date_available=datetime.date(int(date_available[6:]),int(date_available[3:5]),int(date_available[0:2]))
            m.amount=itastr2amount(amount_str)

            m.information={}
            m.correspondent_name=None
            m.correspondent_id=None
    

            try:

                if method=="PAGAMENTO CARTA":
                    time_info=re.search(" alle ore ([0-9]+):([0-9]+)",description)
                    m.information["time"]=datetime.time(int(time_info[1]),int(time_info[2]))
                    m.method="card"
                    if re.search("Tasso di cambio",description):
                        currency_info=re.search(" presso ([A-Za-z0-9. ]+)Tasso di cambio ([A-Z]+)/([A-Z]+)=([-+0-9,]+)$",description)
                        m.correspondent_name=currency_info[1]
                        m.information["currency"]=currency_info[2]
                        m.information["exchange_rate"]=float(re.sub(",",".",currency_info[4]))
                        m.information["amount_currency"]=-engstr2amount(re.search(" Importo in divisa=([0-9.,]+) ",description)[1])
                        
                    elif re.search(" - Transazione C-less$",description):
                        m.information["contactless"]=True
                        m.correspondent_name=re.search(" presso ([A-Za-z0-9. ]+) - Transazione C-less$",description)[1]
                    else:
                        m.information["contactless"]=False
                        m.correspondent_name=re.search(" presso ([A-Za-z0-9. ]+)",description)[1]

                elif method=="PRELIEVO CARTA":
                    time_info=re.search(" alle ore ([0-9]+):([0-9]+)",description)
                    m.information["time"]=datetime.time(int(time_info[1]),int(time_info[2]))
                    c=re.search(" Div=([A-Z]+) ",description)[1]
                    if c!="EUR":
                        m.information["currency"]=c
                        m.information["amount_currency"]=-engstr2amount(re.search(" Importo in divisa=([0-9.,]+) ",description)[1])
                        
                    m.information["place"]=re.search(" presso ([A-Za-z0-9. ]+)",description)[1]

                    m.method="cash_withdrawal"
    
                elif method=="ACCR. STIPENDIO-PENSIONE":
                    m.information["transaction_id"]=re.search("Bonifico N\\. ([A-Za-z0-9]+)",description)[1]
                    m.correspondent_id=re.search("Codifica Ordinante ([A-Z0-9]+)",description)[1]
                    m.correspondent_name=re.search("Anagrafica Ordinante ([A-Za-z0-9. ]+) Note:",description)[1]
                    m.information["reason"]=re.search("Note: (["+reason_char+"]+)$",description)[1]

                    m.method="wage"

                elif method=="ACCREDITO BONIFICO":
                    m.information["transaction_id"]=re.search("Bonifico N\\. ([A-Za-z0-9]+)",description)[1]
                    m.correspondent_id=re.search("Codifica Ordinante ([A-Z0-9]+)",description)[1]
                    m.correspondent_name=re.search("Anagrafica Ordinante ([A-Za-z0-9. ]+) Note:",description)[1]
                    m.information["reason"]=re.search("Note: (["+reason_char+"]+)$",description)[1]
                
                    m.method="incoming_transfer"

                elif method=="VS.DISPOSIZIONE":
                    if re.search("^BONIFICO DA VOI DISPOSTO NOP",description):
        
                        m.information["transaction_id"]=re.search("^BONIFICO DA VOI DISPOSTO NOP ([A-Za-z0-9]+)",description)[1]
                        m.correspondent_id=re.search(" A FAVORE DI ([A-Za-z0-9. ]+) C. BENEF. ([A-Z0-9]+) NOTE:",description)[2]
                        m.correspondent_name=re.search(" A FAVORE DI ([A-Za-z0-9. ]+) C. BENEF. ([A-Z0-9]+) NOTE:",description)[1]
                        m.information["reason"]=re.search(" NOTE: (["+reason_char+"]+)$",description)[1]
                
                        m.method="incoming_transfer"
            
                    else:
                        information["description"]=reason+' '+description
                        m.method="other"
                        raise LineError(a,information)

                elif method=="PAGAMENTI DIVERSI":
                    if re.search("Addebito SDD CORE",description):
            
                        m.correspondent_id=re.search("Creditor id\\. ([A-Z0-9]+)",description)[1]
                        m.correspondent_name=re.search("Creditor id\\. ([A-Z0-9]+) (["+reason_char+"]+) Id Mandato ",description)[2]
                        tr=re.search(" Rif\\. ([0-9A-Z-]+)$",description)
                        if tr:
                            m.information["transaction_id"]=tr[1]
                        m.information["reason"]=re.search("Id Mandato ([0-9A-Za-z-]+) Debitore",description)[1]
            
                        m.method="sdd"

                    else:
                        m.information["description"]=reason+' '+description
                        m.method="other"
                        raise LineError(a,m.information)

                elif method=="BOLLI GOVERNATIVI":
                    m.method="bolli_governativi"
                    m.information["description"]="bolli_governativi"

                elif method=="Canone servizio SMS OTP":
                    m.method="sms_otp"
                    m.information["description"]="sms_otp"
            

                else:
                    m.information["description"]=reason+' '+description
                    m.method="other"
                    raise LineError(a,information)

            except:
                raise

            return m

        def __lt__(self,obj):
            return (self.date_account < obj.date_account)

        def __le__(self,obj):
            return (self.date_account <= obj.date_account)

        def __gt__(self,obj):
            return (self.date_account > obj.date_account)

        def __ge__(self,obj):
            return (self.date_account >= obj.date_account)

                         
        
        

    def load_xls(string):
        """Consider string as an xls file downloded from the ING website and then 
returns a transaction object, filled with the proper information"""

        t=Transactions()
        interval=re.search("""Nella tabella vedi elencate le operazioni dal ([0-9]+)/([0-9]+)/([0-9]+) al ([0-9]+)/([0-9]+)/([0-9]+)</td>""",string)
        t.start_date=datetime.date(int(interval[3]),int(interval[2]),int(interval[1]))
        t.end_date=datetime.date(int(interval[6]),int(interval[5]),int(interval[4]))
        t.account_number=int(re.search("""<b>Conto Corrente Arancio n.:</b> ([0-9]+)""",string)[1])
        t.iban=re.search("""<td colspan="5" border="1"><b>IBAN:</b> ([0-9A-Z]+)</td>""",string)[1]
        t.end_account=itastr2amount(re.search("""><b>Saldo contabile al</b> ([0-9]+)/([0-9]+)/([0-9]+) ([-+0-9,.]+) &euro;</td>""",string)[4])


        t.movements=[]
        t.start_account=t.end_account

        for i in re.findall("""<tr><td border="1">(.+?)</tr>""",string):
            m=Transactions.Movement.load_xls_line(i)
            t.movements.append(m)
            t.start_account=t.start_account-m.amount

        t.initialized=True
        return t

    def load_json(string):
        dateft="%Y-%m-%d"
        timeft="%H:%M:%S"
        def decoder(obj):
            def datetime_parser(i,j):
                if "date" in i:
                    return datetime.date.fromisoformat(j)
                if "time" in i:
                    return datetime.time.fromisoformat(j)
                return j
            
            if "__Movement__" in obj:
                m=Transactions.Movement()
                for i,j in obj.items():
                    if i=="__Movement__":
                        continue
                    m.__setattr__(i,datetime_parser(i,j))

                return m

            if "__Transactions__" in obj:
                t=Transactions()
                for i,j in obj.items():
                    if i=="__Movement__":
                        continue
                    t.__setattr__(i,datetime_parser(i,j))

                t.initialized=True

                return t

            for i in obj:
                obj[i]=datetime_parser(i,obj[i])
            return obj

        return json.loads(string,object_hook=decoder)
        

    
    def daily_amount(self, start=None, end=None):
        dt=datetime.timedelta(days=1)
        if start==None:
            start=self.start_date
        if end==None:
            end=self.end_date+dt

        if start<self.start_date or end>self.end_date:
            raise RangeError
        
        t=self.start_date
        current_amount=self.start_available
        ret=[]
        for i in self.movements:
            while t<i.date_available:
                if t==end:
                    return ret
                if t>=start:
                    ret.append((t,current_amount))

                t=t+dt
                
            current_amount=current_amount+i.amount

        while t<end:
            ret.append((t,amount))
            t=t+dt

        return ret


    def dump_json(self, indent=4):
        return json.dumps(self,cls=_jencoder, indent=indent)
    
def main(filename):
    
    if filename[-3:]=='csv':
        transactions=csv2transaction_list(filename)
    elif filename[-3:]=='xls':
        transactions=xls2transaction_list(filename)
    else:
        print(sys.stderr,"{%s}: bad extension.".format(filename))
        return 1
                  
    expenses={}

    revenue=0
    expenditure=0

    begindate=datetime.date(1900,1,1)
    
    for info in transactions:
        
        if info["date1"]>=begindate:
            c='other'
            if 'correspondent_name' in info:
                c=info['correspondent_name']

            try:
                if info["method"]=="cash_withdrawal":
                    c="cash_withdrawal"
            except:
                print(info)
                raise
        
            if not c in expenses:
                expenses[c]=0

            expenses[c]=expenses[c]+info['amount']
            if info['amount']>=0:
                revenue=revenue+info['amount']
            else:
                expenditure=expenditure+info['amount']
            

    

    for i in sorted(expenses,key=expenses.__getitem__):
        print(i+":",expenses[i]/100)


    print('\nTotal revenue:', revenue/100)
    print('Total expenditure:', expenditure/100)
    print('Difference: ', (revenue+expenditure)/100)
    return 0


import argparse



def main2(arg):
    parser = argparse.ArgumentParser(description='Analize ING-generated bank account data.')
    
    parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
#    parser.add_argument('--from-date', '-f', nargs=1, default='1900-01-01', 
    

    

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
