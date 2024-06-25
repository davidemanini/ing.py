#! /usr/bin/python3

import re
import sys
import datetime
import time
import json
import csv
import os
import itertools

def itastr2amount(s):
    a=s.replace('.','').replace(',','.')
    return round(100*float(a))


def engstr2amount(s):

    # maybe there's a swap function ...
    return itastr2amount((s.replace(',','')).replace('.',','))


class LineError(Exception):
    def __init__(self, method, description):
        self.method = method
        self.description = description

    def __str__(self):
        return "LineError\nMethod: "+self.method+"\nDescription: "+self.description


class UnknownMethodError(LineError):

    def __str__(self):
        return "Unknown method\nMethod: "+self.method+"\nDescription: "+self.description






class _jencoder(json.JSONEncoder):
    def default(self, obj):
        dateft="%Y-%m-%d"
        timeft="%H:%M:%S"
        if isinstance(obj, Account.Movement):
            data = {  "__Movement__": True,
                      "date_account": obj.date_account,
                      "date_available": obj.date_available,
                      "amount": obj.amount,
                      "method": obj.method,
                      "correspondent_name": obj.correspondent_name,
                      "correspondent_id": obj.correspondent_id,
                      "details": obj.details }
            return data

        if isinstance(obj, Account):
            data = { "__Account__": True,
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






class Account:
    def __init__(self):
        self.initialized=False


    class Movement:
        def __init__(self):
            pass


        def load_line(date_account,date_available,amount,method,description):
            m=Account.Movement()

            m.date_account=date_account
            m.date_available=date_available
            m.amount=amount

            m.details={}
            m.correspondent_name=None
            m.correspondent_id=None

            reason_char='/\'\\(\\)A-Za-z0-9 .,-'


            if method=="PAGAMENTO CARTA" or method=="Pagamento Carta":
                time_info=re.search(" alle ore ([0-9]+):([0-9]+)",description)
                m.details["time"]=datetime.time(int(time_info[1]),int(time_info[2]))
                m.method="card"
                if re.search("Tasso di cambio",description):
                    currency_info=re.search(" presso ([A-Za-z0-9. /*_-]+).Tasso di cambio ([A-Z]+)/([A-Z]+)=([-+0-9,]+)",description)
                    m.correspondent_name=currency_info[1]
                    m.details["currency"]=currency_info[2]
                    m.details["exchange_rate"]=float(re.sub(",",".",currency_info[4]))
                    m.details["amount_currency"]=-engstr2amount(re.search(" Importo in divisa=([0-9.,]+) ",description)[1])

                elif re.search(" - Transazione C-less$",description):
                    m.details["contactless"]=True
                    m.correspondent_name=re.search(" presso ([A-Za-z0-9. \\*\\&\\'-]+) - Transazione C-less$",description)[1]
                    if re.search("Pagamenti trasporti modalita\\' contactless",description):
                        m.details["trasportation"]=True
                else:
                    m.details["contactless"]=False
                    m.correspondent_name=re.search(" presso ([A-Za-z0-9. ]+)",description)[1]


            elif method=="Carta Credito ING ":
                m.method="credit_card"

            elif method=="ADDEBITO CARTA DI CREDITO" or method=="Addebito Carta Di Credito":
                m.method="credit_card"

            elif method=="Trasferimento in accredito":
                time_info=re.search(" alle ore ([0-9]+):([0-9]+)",description)
                m.details["time"]=datetime.time(int(time_info[1]),int(time_info[2]))
                m.method="card_transfer"
                m.correspondent_name=re.search(" presso ([A-Za-z0-9. ]+)",description)[1]


            elif method=="PRELIEVO CARTA" or method=="Prelievo Carta":
                time_info=re.search(" alle ore ([0-9]+):([0-9]+)",description)
                m.details["time"]=datetime.time(int(time_info[1]),int(time_info[2]))
                c=re.search(" Div=([A-Z]+) ",description)[1]
                if c!="EUR":
                    m.details["currency"]=c
                    m.details["amount_currency"]=-engstr2amount(re.search(" Importo in divisa=([0-9.,]+) ",description)[1])

                m.details["place"]=re.search(" presso ([A-Za-z0-9. ]+)",description)[1]

                m.method="cash_withdrawal"

            elif method=="ACCR. STIPENDIO-PENSIONE" or method=="ACCREDITO STIPENDIO-PENSIONE" or method=="Accredito Stipendio/Pensione":
                m.details["transaction_id"]=re.search("Bonifico N\\. ([A-Za-z0-9]+)",description)[1]
                m.correspondent_id=re.search("Codifica Ordinante ([A-Z0-9]+)",description)[1]
                m.correspondent_name=re.search("Anagrafica Ordinante ([A-Za-z0-9. ]+) Note:",description)[1]
                m.details["reason"]=re.search("Note: (["+reason_char+"]+)$",description)[1]

                m.method="wage"

            elif method=="ACCREDITO BONIFICO" or method=="Accredito Bonifico":
                m.details["transaction_id"]=re.search("Bonifico N\\. ([A-Za-z0-9]+)",description)[1]
                m.correspondent_id=re.search("Codifica Ordinante ([A-Z0-9]+)",description)[1]
                m.correspondent_name=re.search("Anagrafica Ordinante ([-A-Za-z0-9. ]+) Note:",description)[1]
                m.details["reason"]=re.search("Note: (["+reason_char+"]*)$",description)[1]

                m.method="incoming_transfer"

            elif method=="VS.DISPOSIZIONE" or method=="BONIFICO IN USCITA" or method=="Bonifico In Uscita":
                if re.search("^BONIFICO DA VOI DISPOSTO NOP",description):

                    m.details["transaction_id"]=re.search("^BONIFICO DA VOI DISPOSTO NOP ([A-Za-z0-9]+)",description)[1]
                    m.correspondent_id=re.search(" A FAVORE DI ([A-Za-z0-9. ]+) C. BENEF. ([A-Z0-9]+) NOTE:",description)[2]
                    m.correspondent_name=re.search(" A FAVORE DI ([A-Za-z0-9. ]+) C. BENEF. ([A-Z0-9]+) NOTE:",description)[1]
                    m.details["reason"]=re.search(" NOTE: (["+reason_char+"]+)$",description)[1]

                    m.method="incoming_transfer"

                else:
                    raise LineError(method, description)
    
            elif method=="GIRO VERSO MIEI CONTI":
                try:

                    m.correspondent_id=re.search("^A  ([A-Z0-9]+) ([A-Za-z0-9. ]+)",description)[1]
                    m.details["reason"]=re.search("^A  ([A-Z0-9]+) ([A-Za-z0-9. ]+)",description)[2]

                    m.method="giro_transfer"

                except:
                    raise LineError(method, description)

                
            elif method=="GIROCONTO" or method=="Giroconto":

                info=re.search("^DA ([A-Z0-9]+) GIRO da",description)
                if info!=None:                        
                    m.correspondent_id=info[1]
                    m.method="incoming_giro_transfer"
                        
                elif re.search("^A  ([A-Z0-9]+) ([A-Za-z0-9. ]+)",description)!=None:
                    info=re.search("^A  ([A-Z0-9]+) ([A-Za-z0-9. ]+)",description)
                    m.correspondent_id=info[1]
                    m.details["reason"]=info[2]
                    m.method="outgoing_giro_transfer"
                        
                else:
                    raise LineError(method, description)
                
            elif method=="PAGAMENTI DIVERSI":
                if re.search("Addebito SDD CORE",description):

                    m.correspondent_id=re.search("Creditor id\\. ([A-Z0-9]+)",description)[1]
                    m.correspondent_name=re.search("Creditor id\\. ([A-Z0-9]+) (["+reason_char+"]+) Id Mandato ",description)[2]
                    tr=re.search(" Rif\\. ([0-9A-Z-]+)$",description)
                    if tr:
                        m.details["transaction_id"]=tr[1]
                    m.details["reason"]=re.search("Id Mandato ([0-9A-Za-z-]+) Debitore",description)[1]

                    m.method="sdd"

                elif re.search("Pagamento CBILL  PAGO PA",description):
                    m.method="cbill"
                    m.correspondent_name=re.search("Pagamento CBILL  PAGO PA a favore di ([A-Za-z0-9. ]+) di importo",description)[1]
                    m.details["transaction_id"]=re.search("Identificativo transazione ([0-9]+), Numero bolletta",description)[1]
                    m.details["reason_id"]=re.search("Numero bolletta ([0-9]+) Commissione azienda",description)[1]
                    m.details["reason"]=re.search("euro. CAUSALE: (["+reason_char+"]+)",description)[1]

                else:
                    raise LineError(method, description)

            elif method=="ADDEBITO DIRETTO" or method=="Addebito Diretto":
                if re.search("Addebito SDD CORE",description):

                    m.correspondent_id=re.search("Creditor id\\. ([A-Z0-9]+)",description)[1]
                    m.correspondent_name=re.search("Creditor id\\. ([A-Z0-9]+) (["+reason_char+"]+) Id Mandato ",description)[2]
                    tr=re.search(" Rif\\. ([0-9A-Z-]+)$",description)
                    if tr:
                        m.details["transaction_id"]=tr[1]
                    m.details["reason"]=re.search("Id Mandato ([0-9A-Za-z-]+) Debitore",description)[1]

                    m.method="sdd"

            elif method=="BOLLI GOVERNATIVI" or method=="Bolli Governativi":
                m.method="bolli_governativi"
                m.details["description"]="bolli_governativi"

            elif method=="Canone servizio SMS OTP" or method=="Canone Servizio Sms Otp":
                m.method="sms_otp"
                m.details["description"]="sms_otp"

            elif method=="COMMISSIONI":
                m.method="commissioni"
                m.details=description

            elif method=="Canone Mensi.Servizio di Consu" or method=="Canone Mens. Servizio Di Consulenza":
                m.method="consulence"
                m.details["dossier_id"]=re.search("Canone Mensile Servizio di Consulenza dossier numero ([0-9]+)",description)[1]

            elif method=="IMPOSTA DI BOLLO INVESTIMENTI":
                m.method="bolli_investimenti"
                m.details["dossier_id"]=re.search("Imposta di bollo IA dossier ([0-9]+)",description)[1]
                
            elif method=="Acquisto fondi":
                m.method="fund"
                fund_info=re.search("Acquisto quote del fondo ([A-Z ]+) su dossier ([0-9]+)",description)
                m.details["fund_name"]=fund_info[1]
                m.details["dossier_id"]=fund_info[2]

                
            elif method=="Vendita Fondi" or method=="VENDITA FONDI":
                m.method="fund"
                fund_info=re.search("Vendita quote del fondo ([A-Z ]+) su dossier ([0-9]+)",description)
                m.details["fund_name"]=fund_info[1]
                m.details["dossier_id"]=fund_info[2]

            elif method=="SPESE ASSEGNO CIRCOLARE NON TR":
                m.method="spese_assegno_circolare"

            elif method=="EMISS.ASSEGNO CIRCOLARE":
                m.method="assegno_circolare"

            elif method=="Accredito Dividendi Fondi" or method=="ACCREDITO DIVIDENDI FONDI":
                m.method="fund_dividend"
                c=re.search("Incasso dividendo del fondo ([A-Z ]+)              n. azioni      ([0-9,]+) importo unitario        1,0000000 al netto imposta     ([0-9,]+) euro", description)
                m.details["fund_name"]=c[1]
                m.details["shares_no"]=float(re.sub(",",".",c[2]))
                m.details["tax"]=float(re.sub(",",".",c[3]))

            elif method=="CANONE CARTA DI CREDITO" or method=="Canone Carta Di Credito":
                m.method="credit_card_canon"

                
            else:
                raise UnknownMethodError(method, description)


            return m

        def __lt__(self,obj):
            return (self.date_account < obj.date_account)

        def __le__(self,obj):
            return (self.date_account <= obj.date_account)

        def __gt__(self,obj):
            return (self.date_account > obj.date_account)

        def __ge__(self,obj):
            return (self.date_account >= obj.date_account)


        def load_xls_line(line):
            l=re.search("""([0-9/]+)</td><td border="1">([0-9/]+)</td><td border="1">(.+)</td><td border="1">(.+)</td><td class="excelCurrency" border="1">&euro; ([-+0-9,.]+)</td>""",line)

            date_account=datetime.datetime.strptime(l[1],'%d/%m/%Y').date()
            date_available=datetime.datetime.strptime(l[2],'%d/%m/%Y').date()
            amount=itastr2amount(l[5])

            return Account.Movement.load_line(date_account,date_available,amount,l[3],l[4])


        
    def load_xls(f):
        """Consider string as an xls file downloded from the ING website and then
returns a transaction object, filled with the proper information"""

        string=f.read()
        t=Account()
        interval=re.search("""Nella tabella vedi elencate le operazioni dal ([0-9]+)/([0-9]+)/([0-9]+) al ([0-9]+)/([0-9]+)/([0-9]+)</td>""",string)
        t.start_date=datetime.date(int(interval[3]),int(interval[2]),int(interval[1]))
        t.end_date=datetime.date(int(interval[6]),int(interval[5]),int(interval[4]))
        t.account_number=int(re.search("""<b>Conto Corrente Arancio n.:</b> ([0-9]+)""",string)[1])
        t.iban=re.search("""<td colspan="5" border="1"><b>IBAN:</b> ([0-9A-Z]+)</td>""",string)[1]
        t.end_account=itastr2amount(re.search("""><b>Saldo contabile al</b> ([0-9]+)/([0-9]+)/([0-9]+) ([-+0-9,.]+) &euro;</td>""",string)[4])


        t.movements=[]
        t.start_account=t.end_account

        for i in re.findall("""<tr><td border="1">(.+?)</tr>""",string):
            m=Account.Movement.load_xls_line(i)
            t.movements.append(m)
            t.start_account=t.start_account-m.amount

        t.movements.sort()
        t.initialized=True
        return t

    def load_csv(f):
        t=Account()
        t.iban=f.name.split("_")[0]
        t.movements=[]

        # Not sure about this
        t.account_number=int(t.iban[-6:])
        
        reader=csv.DictReader(f,delimiter=';')

        for i in reader:

            if i["DESCRIZIONE OPERAZIONE"]=="Saldo iniziale":
                t.start_account=itastr2amount(i["ENTRATE"])
                t.start_date=datetime.datetime.strptime(i["DATA CONTABILE"],'%d/%m/%Y').date()
            elif i["DESCRIZIONE OPERAZIONE"]=="Saldo finale":
                t.end_account=itastr2amount(i["ENTRATE"])
                t.end_date=datetime.datetime.strptime(i["DATA CONTABILE"],'%d/%m/%Y').date()
            else:
                amount=0
                if i["USCITE"]=="":
                    amount=itastr2amount(i["ENTRATE"])
                else:
                    amount=itastr2amount(i["USCITE"])

                account_date=datetime.datetime.strptime(i["DATA CONTABILE"],'%d/%m/%Y').date()
                available_date=datetime.datetime.strptime(i["DATA VALUTA"],'%d/%m/%Y').date()
                m=Account.Movement.load_line(account_date,available_date,amount,i["CAUSALE"],i["DESCRIZIONE OPERAZIONE"])
                t.movements.append(m)
                

        t.movements.sort()
        t.initialized=True
        return t
        

    def load_json(f):
        def decoder(obj):
            def datetime_parser(i,j):
                if "date" in i:
                    return datetime.date.fromisoformat(j)
                if "time" in i:
                    return datetime.time.fromisoformat(j)
                return j

            if "__Movement__" in obj:
                m=Account.Movement()
                for i,j in obj.items():
                    if i=="__Movement__":
                        continue
                    m.__setattr__(i,datetime_parser(i,j))

                return m

            if "__Account__" in obj:
                t=Account()
                for i,j in obj.items():
                    if i=="__Account__":
                        continue
                    t.__setattr__(i,datetime_parser(i,j))

                t.initialized=True

                return t

            for i in obj:
                obj[i]=datetime_parser(i,obj[i])
            return obj

        return json.load(f,object_hook=decoder)

    def dump_json(self, indent=4):
        if not self.initialized:
            return json.dumps(None, indent=indent)
        return json.dumps(self,cls=_jencoder, indent=indent)


    def daily_amount(self, start=None, end=None):
        assert self.initialized,"Not initialized account"
        dt=datetime.timedelta(days=1)
        if start==None:
            start=self.start_date
        if end==None:
            end=self.end_date


        assert start<=end,"End is before start"
        assert (start>=self.start_date and end<=self.end_date),"Range error"
#            raise RangeError

        t=self.start_date
        current_amount=self.start_account
        ret=[]
        for i in sorted(self.movements):
            while t<i.date_account:
                if t>end:
                    return ret
                if t>=start:
                    ret.append((t,current_amount))

                t=t+dt

            current_amount=current_amount+i.amount

        while t<=end:
            ret.append((t,current_amount))
            t=t+dt

        return ret

    def cut_before(self, end):
        assert self.initialized,"Not initialized account"
        assert end>self.start_date,"Range error"
        dt=datetime.timedelta(days=1)

        end=min(end, self.end_date+dt)

        ret=Account()
        ret.iban=self.iban
        ret.account_number=self.account_number
        ret.start_date=self.start_date
        ret.start_account=self.start_account

        ret.movements=[]
        ret.end_date=end-dt
        ret.end_account=ret.start_account

        ret.initialized=True
        for i in sorted(self.movements):
            if i.date_account>=end:
                return ret
            ret.movements.append(i)
            ret.end_account=ret.end_account+i.amount
        return ret


    def cut_notbefore(self, start):
        assert self.initialized,"Not initialized account"
        assert start<=self.end_date,"Range error"
        dt=datetime.timedelta(days=1)

        start=max(start, self.start_date)

        ret=Account()
        ret.iban=self.iban
        ret.account_number=self.account_number
        ret.end_date=self.end_date
        ret.end_account=self.end_account

        ret.movements=[]
        ret.start_date=start
        ret.start_account=ret.end_account

        ret.initialized=True
        for i in sorted(self.movements, reverse=True):
            if i.date_account<start:
                return ret
            ret.movements.append(i)
            ret.start_account=ret.start_account-i.amount
        return ret

    def cut_after(self, start):
        assert self.initialized,"Not initialized account"
        assert start<self.end_date,"Range error"
        dt=datetime.timedelta(days=1)

        start=max(start, self.start_date-dt)

        ret=Account()
        ret.iban=self.iban
        ret.account_number=self.account_number
        ret.end_date=self.end_date
        ret.end_account=self.end_account

        ret.movements=[]
        ret.start_date=start+dt
        ret.start_account=ret.end_account

        ret.initialized=True
        for i in sorted(self.movements, reverse=True):
            if i.date_account<=start:
                return ret
            ret.movements.append(i)
            ret.start_account=ret.start_account-i.amount
        return ret

    def cut_notafter(self, end):
        assert self.initialized,"Not initialized account"
        assert end>=self.start_date,"Range error"
        dt=datetime.timedelta(days=1)

        end=min(end, self.end_date)

        ret=Account()
        ret.iban=self.iban
        ret.account_number=self.account_number
        ret.start_date=self.start_date
        ret.start_account=self.start_account

        ret.movements=[]
        ret.end_date=end
        ret.end_account=ret.start_account

        ret.initialized=True
        for i in sorted(self.movements):
            if i.date_account>end:
                return ret
            ret.movements.append(i)
            ret.end_account=ret.end_account+i.amount
        return ret




    def join(self,t):
        assert (self.account_number==t.account_number and self.iban==t.iban),"Different accounts"
        assert (self.end_date>t.start_date or t.end_date>self.start_date),"Non-intersecting ranges"

        if self.end_date>t.start_date:
            cut_date=t.start_date+(self.end_date-t.start_date)/2
            ret=self.cut_before(cut_date)
            t2=t.cut_notbefore(cut_date)
            # The following assertion should never be false!
            assert ret.end_account==t2.start_account,"Non matching accounts.  Please report this error"
            ret.movements=ret.movements+t2.movements
            ret.end_date=t2.end_date
            ret.end_account=t2.end_account
            return ret

        return t.join(self)

    def check_amount(self):
        a=self.start_account-self.end_account
        for i in self.movements:
            a=a+i.amount
        return a


def load_db(data_dir=None):
    if data_dir==None:
        data_dir=os.environ['HOME']+'/.ing'
    data_file=data_dir+"/db.json"
    f=open(data_file,"r")
    db=Account.load_json(f)
    f.close()
    assert db.initialized, "The database file "+data_file+" is not initialized"
    return db


def add_to_db(f,data_dir=None):

    if f.name[-3:]=='xls':
        output_file=data_dir+"/"+date_str+".xls"
        t=Account.load_xls(f)
    elif f.name[-3:]=='csv':
        output_file=data_dir+"/"+f.name
        t=Account.load_csv(f)
    elif f.name[-4:]=='json':
        # this last case should never occour
        output_file=data_dir+"/"+date_str+".json"
        t=Account.load_json(f)
    else:
        print("Error: format not known.", file=sys.stderr)
        raise Exception

    f.seek(0)
    s=f.read()
    f.close()
    
    assert t.initialized,"Account must be initialized"
    if data_dir==None:
        data_dir=os.environ['HOME']+'/.ing'
    date_str=datetime.datetime.today().strftime("%Y-%m-%dT%H:%M:%S")
    if not os.path.isdir(data_dir):
        os.mkdir(data_dir)
        print("Created data directory "+data_dir+".", file=sys.stderr)

    data_file=data_dir+"/db.json"
    if os.path.isfile(data_file):
        f=open(data_file,"r")
        db=Account.load_json(f)
        f.close()
        assert db.initialized, "The database file "+data_file+" is not initialized"

        if db.end_date>=t.end_date:
            print("No newer information is provided. Quitting...", file=sys.stderr)
            return 0
        assert db.end_date>t.start_date,"Error: provided data do not intersect current database"

        new_db=db.join(t)

        os.rename(data_file,data_dir+"/db."+date_str+".json")

        f=open(data_file,"w")
        f.write(new_db.dump_json())
        f.close()
    else:
        f=open(data_file,"w")
        f.write(t.dump_json())
        f.close()

    if output_file is not None:
        f=open(output_file,"w")
        f.write(s)
        f.close()







def main(arg,environ=os.environ):
    import argparse


    parser = argparse.ArgumentParser(description='Analize ING-generated bank account data.')


    parser.add_argument('--input', dest='input_file', type=argparse.FileType('r'), default=None)
    parser.add_argument('--output', dest='output_file', type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument('--data-dir', dest='data_dir', type=str, default=None)

    parser.add_argument('--before',type=datetime.date.fromisoformat, default=None)
    parser.add_argument('--after',type=datetime.date.fromisoformat, default=None)
    parser.add_argument('--not-after',type=datetime.date.fromisoformat, default=None)
    parser.add_argument('--not-before',type=datetime.date.fromisoformat, default=None)

    action = parser.add_mutually_exclusive_group()
    action.add_argument('--to-json', action='store_true')
    action.add_argument('--add-to-db', action='store_true')
    action.add_argument('--daily-amount', action='store_true')
    action.add_argument('--plot-amount', action='store_true')
    a = parser.parse_args(arg)

    if a.data_dir==None:
        data_dir=environ['HOME']+'/.ing'
    else:
        data_dir=a.data_dir

    def cutter(t):
        ret=t
        if a.before:
            ret=ret.cut_before(a.before)
        if a.after:
            ret=ret.cut_after(a.after)
        if a.not_before:
            ret=ret.cut_notbefore(a.not_before)
        if a.not_after:
            ret=ret.cut_notafter(a.not_after)
        return ret

    if a.input_file is None:
        try:
            a.input_file=open(data_dir+"/db.json","r")
        except FileNotFoundError:
            print("You must provide an input file (the database is not initialized).",file=sys.stderr)
            return 1

    decoder=Account.load_json
    if a.input_file.name[-3:]=="xls":
        decoder=Account.load_xls
    elif a.input_file.name[-3:]=="csv":
        decoder=Account.load_csv
    if a.to_json:
        t=cutter(decoder(a.input_file))
        a.input_file.close()
        a.output_file.write(t.dump_json())
        a.output_file.close()
        return 0
    elif a.add_to_db:
        if a.input_file.name==data_dir+"/db.json":
            print("Error: an input file must be specified.",file=sys.stderr)
            return 1
        try:
            add_to_db(a.input_file,data_dir)
        except OSError as e:
            print(e, file=sys.stderr)
            return 1
        except Exception as e:
            print(e, file=sys.stderr)
            raise
        return 0

    elif a.daily_amount:
        t=cutter(decoder(a.input_file))
        a.input_file.close()
        daily_amount=t.daily_amount()
        print("date,amount",file=a.output_file)
        for i in daily_amount:
            print(str(i[0])+",%.2f"%(i[1]/100),file=a.output_file)

        a.output_file.close()
        return 0

    elif a.plot_amount:

        t=cutter(decoder(a.input_file))
        a.input_file.close()
        daily_amount=t.daily_amount()

        x=[i[0] for i in daily_amount]
        y=[i[1]/100 for i in daily_amount]
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
        except ModuleNotFoundError:
            print("Error: matplotlib is not installed.\nTry something like ``sudo apt-get install python3-matplotlib",file=sys.stderr)

        fig, ax = plt.subplots(constrained_layout=True)
        locator = mdates.AutoDateLocator()
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)

        ax.plot(x,y,"-+")
        plt.xlabel("date")
        plt.ylabel("amount")
        plt.grid(ls=":")
        plt.show()
    else:
        print("Error: an action must be specified.", file=sys.stderr)
        return 1

if __name__ == "__main__":
    import os
    sys.exit(main(sys.argv[1:],os.environ))
