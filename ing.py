#! /usr/bin/python3

import re
import sys
import datetime
import time



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

def process_line(a):

    reason_char='\'\\(\\)A-Za-z0-9 .,-'
    
    information={}
    information["date1"]=datetime.date(int(a[0][6:]),int(a[0][3:5]),int(a[0][0:2]))
    information["date2"]=datetime.date(int(a[1][6:]),int(a[1][3:5]),int(a[1][0:2]))
    information["amount"]=itastr2amount(a[4])
    
    field=a[2]

    if field=="PAGAMENTO CARTA":
        time_info=re.search(" alle ore ([0-9]+):([0-9]+)",a[3])
        information["time"]=datetime.time(int(time_info[1]),int(time_info[2]))
        information["currency"]=re.search(" Div=([A-Z]+) ",a[3])[1]
        information["amount_currency"]=-engstr2amount(re.search(" Importo in divisa=([0-9.,]+) ",a[3])[1])
        if re.search(" - Transazione C-less$",a[3]):
            information["contactless"]=1
            information["correspondent_name"]=re.search(" presso ([A-Za-z0-9. ]+) - Transazione C-less$",a[3])[1]
        else:
            information["correspondent_name"]=re.search(" presso ([A-Za-z0-9. ]+)",a[3])[1]

        information["field"]="card"

    elif field=="PRELIEVO CARTA":
        time_info=re.search(" alle ore ([0-9]+):([0-9]+)",a[3])
        information["time"]=datetime.time(int(time_info[1]),int(time_info[2]))
        information["currency"]=re.search(" Div=([A-Z]+) ",a[3])[1]
        information["amount_currency"]=-engstr2amount(re.search(" Importo in divisa=([0-9.,]+) ",a[3])[1])
        information["place"]=re.search(" presso ([A-Za-z0-9. ]+)",a[3])[1]

        information["field"]="cash_withdrawal"
    
    elif field=="ACCR. STIPENDIO-PENSIONE":
        information["transaction_id"]=re.search("Bonifico N\\. ([A-Za-z0-9]+)",a[3])[1]
        information["correspondent_id"]=re.search("Codifica Ordinante ([A-Z0-9]+)",a[3])[1]
        information["correspondent_name"]=re.search("Anagrafica Ordinante ([A-Za-z0-9. ]+) Note:",a[3])[1]
        information["reason"]=re.search("Note: (["+reason_char+"]+)$",a[3])[1]

        information["field"]="wage"

    elif field=="ACCREDITO BONIFICO":
        information["transaction_id"]=re.search("Bonifico N\\. ([A-Za-z0-9]+)",a[3])[1]
        information["correspondent_id"]=re.search("Codifica Ordinante ([A-Z0-9]+)",a[3])[1]
        information["correspondent_name"]=re.search("Anagrafica Ordinante ([A-Za-z0-9. ]+) Note:",a[3])[1]
        information["reason"]=re.search("Note: (["+reason_char+"]+)$",a[3])[1]
                
        information["field"]="incoming_transfer"

    elif field=="VS.DISPOSIZIONE":
        if re.search("^BONIFICO DA VOI DISPOSTO NOP",a[3]):
        
            information["transaction_id"]=re.search("^BONIFICO DA VOI DISPOSTO NOP ([A-Za-z0-9]+)",a[3])[1]
            information["correspondent_id"]=re.search(" A FAVORE DI ([A-Za-z0-9. ]+) C. BENEF. ([A-Z0-9]+) NOTE:",a[3])[2]
            information["correspondent_name"]=re.search(" A FAVORE DI ([A-Za-z0-9. ]+) C. BENEF. ([A-Z0-9]+) NOTE:",a[3])[1]
            information["reason"]=re.search(" NOTE: (["+reason_char+"]+)$",a[3])[1]
                
            information["field"]="incoming_transfer"
            
        else:
            information["description"]=a[2]+' '+a[3]
            information["field"]="other"

    elif field=="PAGAMENTI DIVERSI":
        if re.search("Addebito SDD CORE",a[3]):
            
            information["correspondent_id"]=re.search("Creditor id\\. ([A-Z0-9]+)",a[3])[1]
            information["correspondent_name"]=re.search("Creditor id\\. ([A-Z0-9]+) (["+reason_char+"]+) Id Mandato ",a[3])[2]
            tr=re.search(" Rif\\. ([0-9A-Z-]+)$",a[3])
            if tr:
                information["transaction_id"]=tr[1]
            information["reason"]=re.search("Id Mandato ([0-9A-Za-z-]+) Debitore",a[3])[1]
            
            information["field"]="sdd"

        else:
            information["description"]=a[2]+' '+a[3]
            information["field"]="other"


    else:
        information["description"]=a[2]+' '+a[3]
        information["field"]="other"
        
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
            if info["field"]=="cash_withdrawal":
                c="cash_withdrawal"
        
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
