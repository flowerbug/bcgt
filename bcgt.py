#!/usr/bin/env python3
"""List Unsold Lots and Generate Buy, Sell and Split Transactions.

The primary purpose of this script is to generate Buy, Sell and Split
beancount transactions.

The secondary purpose of this script is to:

- Produce a table of postings for the assets and liabilities
- Produce a table of per-account attributes
- Produce a table of per-commodity attributes
- Join these tables
- Output them to a CSV file.

Note: This version of the script has been modified to ignore some errors and
to not rearrange the order so it may no longer provide the same output as the
original version.

"""

__copyright__ = "Copyright (C) 2018  Martin Blais"
__copyright__ = "modified by flowerbug@anthive.com"
__license__ = "GNU GPLv2"

from typing import NamedTuple, Tuple, List, Set, Any, Dict
from decimal import Decimal, getcontext, ROUND_HALF_EVEN
from operator import itemgetter
import argparse
import csv
import datetime
import os
import re

from beancount.core.number import ONE
from beancount.core.number import D
from beancount.core import data
from beancount.core import flags
from beancount.core import account
from beancount.core import account_types
from beancount.core import getters
from beancount.ops import summarize
from beancount.core import prices
from beancount.parser import options
from beancount import loader


# Hopefully this is enough digits...
getcontext().prec = 20


Header = List[str]
Rows = List[List[Any]]
Table = NamedTuple('Table', [('header', Header), ('rows', Rows)])


def get_metamap_table(metamap: Dict[str, data.Directive],
                      attributes: List[str],
                      getter) -> Table:
    """Produce a Table of per-commodity attributes."""
    header = attributes
    attrlist = attributes[1:]
    rows = []
    for key, value in metamap.items():
        row = [key]
        for attr in attrlist:
            row.append(getter(value, attr))
        rows.append(row)
    return Table(attributes, sorted(rows))


def get_commodities_table(entries: data.Entries, attributes: List[str]) -> Table:
    """Produce a Table of per-commodity attributes."""
    commodities = getters.get_commodity_directives(entries)
    header = ['currency'] + attributes
    getter = lambda entry, key: entry.meta.get(key, None)
    table = get_metamap_table(commodities, header, getter)
    return table


def get_accounts_table(entries: data.Entries, attributes: List[str]) -> Table:
    """Produce a Table of per-account attributes."""
    oc_map = getters.get_account_open_close(entries)
    accounts_map = {account: dopen for account, (dopen, _) in oc_map.items()}
    header = ['account'] + attributes
    defaults = {'tax': 'taxable',
                'liquid': False}
    def getter(entry, key):
        """Lookup the value working up the accounts tree."""
        value = entry.meta.get(key, None)
        if value is not None:
            return value
        account_name = account.parent(entry.account)
        if not account_name:
            return defaults.get(key, None)
        parent_entry = accounts_map.get(account_name, None)
        if not parent_entry:
            return defaults.get(key, None)
        return getter(parent_entry, key)
    return get_metamap_table(accounts_map, header, getter), accounts_map


def abbreviate_account(acc: str, accounts_map: Dict[str, data.Open]):
    """Compute an abbreviated version of the account name."""

    # Get the root of the account by inspecting the "root: TRUE" attribute up
    # the accounts tree.
    racc = acc
    while racc:
        racc = account.parent(racc)
        dopen = accounts_map.get(racc, None)
        if dopen and dopen.meta.get('root', False):
            acc = racc
            break

    # Remove the account type.
    acc = account.sans_root(acc)

    # Remove the two-letter country code if there is one.
    if re.match(r'[A-Z][A-Z]', acc):
        acc = account.sans_root(acc)

    return acc


def get_postings_table(entries: data.Entries, options_map: Dict,
                       accounts_map: Dict[str, data.Open],
                       threshold: Decimal = D('0.01')) -> Table:
    """Enumerate all the postings."""
    header = ['account',
              'account_abbrev',
              'number',
              'currency',
              'cost_number',
              'cost_currency',
              'cost_date',
              'cost_label']
    balances, _ = summarize.balance_by_account(entries, compress_unbooked=True)
    acctypes = options.get_account_types(options_map)
    rows = []
    for acc, balance in sorted(balances.items()):
        # Keep only the balance sheet accounts.
        acctype = account_types.get_account_type(acc)
        if not acctype in (acctypes.assets, acctypes.liabilities):
            continue

        # Create a posting for each of the positions.
        for pos in balance:
            acc_abbrev = abbreviate_account(acc, accounts_map)
            row = [acc,
                   acc_abbrev,
                   pos.units.number,
                   pos.units.currency,
                   pos.cost.number if pos.cost else ONE,
                   pos.cost.currency if pos.cost else pos.units.currency,
                   pos.cost.date if pos.cost else None,
                   pos.cost.label if pos.cost else None]
            rows.append(row)

    return Table(header, rows)


PRICE_Q = D('0.0000001')


def get_prices_table(entries: data.Entries, main_currency: str) -> Table:
    """Enumerate all the prices seen."""
    price_map = prices.build_price_map(entries)
    header = ['currency', 'cost_currency', 'price_file']
    rows = []
    for base_quote in price_map.keys():
        _, price = prices.get_latest_price(price_map, base_quote)
        if price is None:
            continue
        base, quote = base_quote
        rows.append([base, quote, price.quantize(PRICE_Q)])
    return Table(header, rows)


def get_rates_table(entries: data.Entries,
                    currencies: Set[str],
                    main_currency: str) -> Table:
    """Enumerate all the exchange rates."""
    price_map = prices.build_price_map(entries)
    header = ['cost_currency', 'rate_file']
    rows = []
    for currency in currencies:
        _, rate = prices.get_latest_price(price_map, (currency, main_currency))
        if rate is None:
            continue
        rows.append([currency, rate.quantize(PRICE_Q)])
    return Table(header, rows)


def join(main_table: Table, *col_tables: Tuple[Tuple[Tuple[str], Table]]) -> Table:
    """Join a table with a number of other tables.
    col_tables is a tuple of (column, table) pairs."""

    new_header = list(main_table.header)
    for cols, col_table in col_tables:
        header = list(col_table.header)
        for col in cols:
            assert col in main_table.header
            header.remove(col)
        new_header.extend(header)

    col_maps = []
    for cols, col_table in col_tables:
        indexes_main = [main_table.header.index(col) for col in cols]
        indexes_col = [col_table.header.index(col) for col in cols]
        #indexes_notcol = sorted(set(range(len(col_table.header))) - set(indexes_col))
        col_map = {}
        for row in col_table.rows:
            key = tuple(row[index] for index in indexes_col)
            col_map[key] = row
        assert len(col_map) == len(col_table.rows), cols
        col_maps.append((indexes_main, indexes_col, col_map))

    rows = []
    for row in main_table.rows:
        row = list(row)
        empty_row = [None] * (len(col_table.header) - len(indexes_col))
        for indexes_main, indexes_col, col_map in col_maps:
            key = tuple(row[index] for index in indexes_main)
            other_row = col_map.get(key, None)
            if other_row is not None:
                other_row = list(other_row)
                for index in reversed(indexes_col):
                    del other_row[index]
            else:
                other_row = empty_row
            row.extend(other_row)
        rows.append(row)

    return Table(new_header, rows)


def write_table(table: Table, outfile: str):
    """Write a table to a CSV file."""
    with outfile:
        writer = csv.writer(outfile)
        writer.writerow(table.header)
        writer.writerows(table.rows)

def do_args():
    """Process all of the command arguments."""
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument('filename', help='Beancount input file')

    parser.add_argument('-C', '--currency', action='store',
                        help=("Override the default output currency "
                              "(default is first operating currency)"))

    parser.add_argument('-s', '--switch-acct', action='store_true',
                        help=("Override the default account to REG "
                              "(default is non-taxable ROTH account)"))
    parser.add_argument('-f', '--switch-lot-pref', action='store_true',
                        help=("Override the default lot sale selection order to FIFO"
                              "(default is LIFO)"))

    for shortname, longname in [('-c', 'commodities'),
                                ('-a', 'accounts'),
                                ('-p', 'prices'),
                                ('-r', 'rates'),
                                ('-m', 'postings')]:
        parser.add_argument(
            shortname, '--output_{}'.format(longname),
            type=argparse.FileType('w'),
            help="CSV filename to write out the {} table to.".format(longname))

    parser.add_argument('-o', '--output',
                        type=argparse.FileType('w'),
                        help="CSV filename to write out the final joined table to.")
    return parser.parse_args()


def main():

    args = do_args()

    print ("\nList Stock Lots and (B)Buy, (S)Sell or (X)Split generate Transactions.\n")

    # Accounts used (the -s switch above will change which account to use)
    #   the default is ROTH:, -s toggles it to REG:
    brokerage_acct = "SB:SCH:"
    roth_or_reg = "ROTH:"
    assets = "Assets:"
    income = "Income:"
    equity = "Equity:"
    pnl = "PnL:"
    expenses = "Expenses:"
    fees = "Fees:RegFees"
    mm_acct = "SCHONEMM"

    minus_one = Decimal(-1)

    if args.switch_acct == True:
        print ("Using Regular (taxable) Account")
        roth_or_reg = "REG:"
    else:
        print ("Using ROTH (non-taxable) Account")

    asset_str = assets+brokerage_acct+roth_or_reg
    income_str = income+brokerage_acct+roth_or_reg+pnl
    expenses_str = expenses+brokerage_acct+roth_or_reg+fees
    equity_fees_str = equity+brokerage_acct+roth_or_reg+fees
    mm_str = assets+brokerage_acct+roth_or_reg+mm_acct

    print ("\n  ",asset_str,"\n  ",income_str,"\n  ",expenses_str,"\n  ",equity_fees_str,"\n  ",mm_str,"\n")


    # Lot selection order for Sells -f will change LIFO to FIFO
    if (args.switch_lot_pref != True):
        print ("Lots are Sold in LIFO order.\n")
        lotorder = 'LIFO'
    else:
        print ("Lots are Sold in FIFO order.\n")
        lotorder = 'FIFO'

    # temporary file for generated transactions
    #    append items to tmp_bcgtfile
    #   when finished bcgtfile_name will contain postprocessed
    #     transactions formatted with autobean-format
    bcgtfile_base = "trans-"+roth_or_reg.lower().replace(':','')
    tmp_bcgtfile_name = "/tmp/"+bcgtfile_base+".tmp"
    tmp_bcgtfile = open(tmp_bcgtfile_name, 'a')
    fix_tmp = "/tmp/fix_tmp"
    blankline_tmp = "/tmp/blankline_tmp"
    mk_bl_tmp = "echo > "+blankline_tmp
    bcgtfile_name = bcgtfile_base+"-out.bc"
    bcgtfile = open(bcgtfile_name, 'w')
    postprocess = "autobean-format --indent=\'  \' --currency-column 60 --cost-column 60 --output-mode inplace --thousands-separator add "+tmp_bcgtfile_name
    fix_output = "cat "+tmp_bcgtfile_name+" "+blankline_tmp+" > "+fix_tmp
    move_output = "mv "+fix_tmp+" "+bcgtfile_name
    cleanup_tmpfiles = "rm "+tmp_bcgtfile_name+" "+blankline_tmp

    # Load the file contents.
    entries, errors, options_map = loader.load_file(args.filename)

    # Initialize main output currency.
    main_currency = args.currency or options_map['operating_currency'][0]

    # Get the map of commodities to their meta tags.
    commodities_table = get_commodities_table(
        entries, ['export', 'assetcls', 'strategy', 'issuer'])
    if args.output_commodities is not None:
        write_table(commodities_table, args.output_commodities)

    #print (commodities_table)

    # Get a table of the commodity names.
    #
    # Note: We're fetching the table separately in order to avoid changes to the
    # spreadsheet upstream, and want to tack on the values as new columns on the
    # right.
    names_table = get_commodities_table(entries, ['name'])

    #print (names_table)

    # Get the map of accounts to their meta tags.
    accounts_table, accounts_map = get_accounts_table(
        entries, ['tax', 'liquid'])
    if args.output_accounts is not None:
        write_table(accounts_table, args.output_accounts)

    #print (accounts_table)

    # Enumerate the list of assets.
    postings_table = get_postings_table(entries, options_map, accounts_map)
    if args.output_postings is not None:
        write_table(postings_table, args.output_postings)

    #print (postings_table)

    # Get the list of prices.
    prices_table = get_prices_table(entries, main_currency)
    if args.output_prices is not None:
        write_table(prices_table, args.output_prices)

    #print (prices_table)

    # Get the list of exchange rates.
    index = postings_table.header.index('cost_currency')
    currencies = set(row[index] for row in postings_table.rows)
    rates_table = get_rates_table(entries, currencies, main_currency)
    if args.output_rates is not None:
        write_table(rates_table, args.output_rates)

    #print (rates_table)

    # Join all the tables.
    joined_table = join(postings_table,
                        (('currency',), commodities_table),
                        (('account',), accounts_table),
                        (('currency', 'cost_currency'), prices_table),
                        (('cost_currency',), rates_table),
                        (('currency',), names_table))

    table = Table(joined_table.header, joined_table.rows)

    # Build a smaller table with just the rows we need
    small = []
    try:
        val = None
        for y in range(len(table.rows)):
            x = table.rows[y]
            if ((x[7] is not None) and
               (x[1].startswith('SCH:'+roth_or_reg))):
                acct = x[1]
                chunks = acct.split(":")
                psymbol = chunks[1]+':'+chunks[2]
                nval = x[3]
                if val != nval:
                    #print ('\n')
                    #print (x[3])
                    val = nval
                #print ('   ', f'{x[2]:<{10}.{8}}'.format(),' ', f'{x[4]:<{10}.{8}}'.format(), ' ', x[6], ' ', x[7])
                x.append(psymbol)
                #print (x)
                small.append(x)
        small_table = Table(joined_table.header, small)
    except:
        pass
    #print ('\n\n')


    # I want to sort the table alphabetically on the acct:symbol but
    #   in reverse order on the date and the lot number within the 
    #   date so the most recent trades are listed first.  (aka LIFO
    #   by default.
    class reversor:
        def __init__(self, obj):
            self.obj = obj

        def __eq__(self, other):
            return other.obj == self.obj

        def __lt__(self, other):
            return other.obj < self.obj

    # the default is LIFO, but we can reverse it to FIFO instead
    slist = small_table.rows
    if (args.switch_lot_pref != True):
        slist = sorted(slist, key=lambda y: (y[0].lower(), reversor('{:%Y-%m-%d}'.format(y[6])+y[7])))

    #print (slist[0])

    # I like to see the basis in a certain format

    # this is from the documentation of Decimal
    def moneyfmt(value, places=2, curr='', sep=',', dp='.',
                 pos='', neg='-', trailneg=''):
        """Convert Decimal to a money formatted string.
    
        places:  required number of places after the decimal point
        curr:    optional currency symbol before the sign (may be blank)
        sep:     optional grouping separator (comma, period, space, or blank)
        dp:      decimal point indicator (comma or period)
                 only specify as blank when places is zero
        pos:     optional sign for positive numbers: '+', space or blank
        neg:     optional sign for negative numbers: '-', '(', space or blank
        trailneg:optional trailing minus indicator:  '-', ')', space or blank
    
        >>> d = Decimal('-1234567.8901')
        >>> moneyfmt(d, curr='$')
        '-$1,234,567.89'
        >>> moneyfmt(d, places=0, sep='.', dp='', neg='', trailneg='-')
        '1.234.568-'
        >>> moneyfmt(d, curr='$', neg='(', trailneg=')')
        '($1,234,567.89)'
        >>> moneyfmt(Decimal(123456789), sep=' ')
        '123 456 789.00'
        >>> moneyfmt(Decimal('-0.02'), neg='<', trailneg='>')
        '<0.02>'
    
        """
        q = Decimal(10) ** -places      # 2 places --> '0.01'
        sign, digits, exp = value.quantize(q).as_tuple()
        result = []
        digits = list(map(str, digits))
        build, next = result.append, digits.pop
        if sign:
            build(trailneg)
        for i in range(places):
            build(next() if digits else '0')
        if places:
            build(dp)
        if not digits:
            build('0')
        i = 0
        while digits:
            build(next())
            i += 1
            if i == 3 and digits:
                i = 0
                build(sep)
        build(curr)
        build(neg if sign else pos)
        return ''.join(reversed(result))


    # newmoneyfmt remove trailing zeros, except two
    def newmoneyfmt(value):
        """Convert Decimal to a money formatted string with
        at most two zeroes.
        """

        refsub = re.compile(r"([-+]?(\d{1,3}(,\d{3})+|\d+))(\.)?(\d\d)?(\d*$)")

        mval = moneyfmt(value, places=14, sep=',')

        #print (mval)
        match = refsub.search(mval)
        #print ("match ", match)
        if match is not None:
            #print ("match groups : ", match.groups())
            if int(match.group(5)) == 0:
                newmval = match.group(1)+'.'+match.group(5)
            else:
                newmval = match.group(1)+'.'+match.group(5)+match.group(6).rstrip('0')

        return newmval


    # Buy shares
    def buy_shares(sym, shares_to_buy, price, currency,
        order, btoday, tmpfile):
        """Buy shares and tag this lot with the proper label.
        """

        today_str = '{:%Y-%m-%d}'.format(btoday)
        time_str = '{:%H%M%S}'.format(btoday)
        lot = sym+'-'+today_str+'-'+time_str
        lotstr = '(LOT '+lot+')'
        amt_val = newmoneyfmt((minus_one * Decimal(price) * Decimal(shares_to_buy)))
        #print ("Amt : ", amt_val)
        str1 = today_str+' * \"Bought '+shares_to_buy+' '+sym+' @ '+price+'  '+order+'  '+lotstr+'\"\n'
        #print (str1)
        str2 = '  '+asset_str+sym+'    '+shares_to_buy+' '+sym+' {'+price+' '+currency+', '+today_str+', "'+lot+'"}\n'
        #print (str2)
        str3 = '  '+mm_str+'    '+amt_val+' '+currency+"\n\n"
        #print (str3)
        print (str1, str2, str3, file=tmpfile)


    # Sell shares
    def sell_shares(list, pos, sym, shares_to_sell, price, currency, sregfee,
        order, stoday, tmpfile):
        """Sell shares where the order of lots is determined by how
        the list is sorted (LIFO is the default, FIFO is the other
        option available).  The only error is if the shares do not
        exist.  You can sell all of the shares by specifying a number
        of shares larger than you have.  I do not sell shares short so
        I stop at zero in all cases.  When more than one lot of shares
        are sold the regfee is distributed across the shares in
        proportion to the sizes of the lots or partial lots sold.  With
        rounding being involved if you want precise control of fees
        and lots it is best to sell only each lot at a time and then the
        broker tells you what the fees are for that lot and then put that
        information into this program one lot at a time with the fee.

        Profits and Losses are not classified as short or long term
        yet.
        """

        find_pos = pos
        end = len(list) - 1
        x_sym = list[find_pos][3]
        lot_count = 1
        total_shares = list[find_pos][2]
        this_lot_shares = list[find_pos][2]
        while ((find_pos < end) and (x_sym == list[find_pos+1][3])):
            lot_count += 1
            find_pos += 1
            total_shares += list[find_pos][2]
        finish = find_pos

        #print ("Pos : ", pos)
        #print ("Finish : ", finish)
        #print ("Lot Count : ", lot_count)
        #print ("Total Shares : ", total_shares)

        #print ("Sh_To_Sell : ", shares_to_sell)
        if (shares_to_sell > total_shares):
            print (" Selling all shares")
            shares_to_sell = total_shares
        elif (shares_to_sell > this_lot_shares):
            print (" Selling more than one lot")
        elif (shares_to_sell == this_lot_shares):
            print (" Selling one lot")
        else:
            print (" Selling a part of the lot ")
        whats_left = sregfee
        #print ("sregfee : ", sregfee)
        regfee_per_share = sregfee / shares_to_sell
        #print ("FeePerSh : ", regfee_per_share, "\n")

        sell_pos = pos
        sold_count = 0
        while ((sold_count < shares_to_sell) and (sell_pos <= finish)):
            #print ("Sell Pos : ", sell_pos)
            if (sold_count < shares_to_sell):
                if ((shares_to_sell - sold_count) >= list[sell_pos][2]):
                    sell_these = list[sell_pos][2]
                else:
                    sell_these = shares_to_sell - sold_count
            else:
                sold_count = shares_to_sell

            #print ("\n\n", sell_pos, list[sell_pos])
            lot_shares = list[sell_pos][2]
            lot_date = list[sell_pos][6]
            #print ("Lot_Shares  :", lot_shares)
            #print ("These_Shares  :", sell_these)
            this_regfee = Decimal(regfee_per_share * sell_these).quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN)
            #print ("This Regfee : ", this_regfee)
            if (this_regfee > whats_left):
                #print (" Remaining fee ignored : ", this_regfee - whats_left)
                this_regfee = whats_left
            whats_left -= this_regfee
            #print ("Whats Left : ", whats_left)
            basis_price = list[sell_pos][4]
            #print ("Basis Price : ", basis_price)
            basis_val = basis_price * sell_these
            #print (" Basis Val  : ", newmoneyfmt(basis_val))
            #print (" Sale Price : ", price, "\n")

            sale_value = sell_these * price
            #print (" Sale Value : ", sale_value, "\n")
            sale_pnl = (sale_value - basis_val - this_regfee) * minus_one
            stoday_str = '{:%Y-%m-%d}'.format(stoday)
            lot = list[sell_pos][7]
            lotstr = '(LOT '+lot+')'

            lot_date_str = '{:%Y-%m-%d}'.format(lot_date)
            str0 = stoday_str+' * \"Sold '+str(sell_these)+' '+sym+' @ '+str(price)+' RegFee '+newmoneyfmt(this_regfee)+'  '+order+'  '+lotstr+'\"\n'
            #print ('"Sold', sell_these, sym, '@', price, "RegFee", this_regfee, order, lotstr+'"')
            #print (str0)
            str1 = '  basis: "'+newmoneyfmt(basis_val)+'" \n'
            #print (str1)
            str2 = '  '+asset_str+sym+'    '+str(sell_these * minus_one)+' '+sym+' {'+str(basis_price)+' '+currency+', '+lot_date_str+', "'+lot+'"} @ '+str(price)+' '+currency+'\n'
            #print (str2)
            str3 = '  '+expenses_str+":"+sym+'    '+moneyfmt(minus_one * this_regfee)+' '+currency+'\n'
            #print (str3)
            str4 = '  '+equity_fees_str+'    '+moneyfmt(this_regfee)+' '+currency+'\n'
            #print (str4)
            str5 = '  '+income_str+sym+'    '+moneyfmt(sale_pnl)+' '+currency+'\n'
            #print (str5)
            str6 = '  '+mm_str+'    '+moneyfmt(sale_value - this_regfee)+' '+currency+"\n\n"
            #print (str6)
            print (str0, str1, str2, str3, str4, str5, str6, file=tmpfile)

            sold_count += sell_these
            #print (" lpos : ", sell_pos, "  Sell : ", sell_these)
            #print (" lpos : ", sell_pos, "    Sold : ", sold_count)
            #print (" lpos : ", sell_pos, "     Fee : ", this_regfee)
            if (sold_count == shares_to_sell) and (whats_left != 0.00):
                #print ("\n\nSome Fees not used : ", whats_left, "\n")
                pass
            sell_pos += 1


    print ('\n Shares      Price      Date            Lot Label           Basis')

    # show list
    total = Decimal(0)
    val = None
    for y in range(len(slist)):
        x = slist[y]
        #print (x)
        nval = x[0]
        if val != nval:
            print ('\n')
            print (x[17])
            val = nval
 
        monval = newmoneyfmt(x[2] * x[4])
        total += x[2] * x[14]
 
        print (' ', f'{x[2]:<{9}.{7}}'.format(),f'{x[4]:<{9}.{7}}'.format(), x[6], ' ', '{0: <23}'.format(x[7]), monval)

    #print ("\nTotal : ", newmoneyfmt(total))

    # Keep going until done

    done = False

    while (done == False):

        found = None

        # Buy, Sell, Split or Done
        print ('\n\n(B)Buy, (S)Sell, (X)Split or (D)one\nEnter: \"B <num> <sym> <price>\" or \"S <num> <sym> <price> <regfee>\" or \"X <sym> <anum> FOR <bnum> or \"D\"\n')
        linein = input().upper()
        spl = linein.split()
        #print (spl)
        #print (len(spl))
    
        # we need some input
        if spl is None or spl == []:
           print ("\n\nNeed correct input.")
           continue
        else:
           spl[0] = spl[0][0]

        command = spl[0]
        lot = ''
        lotstr = ''
        if command in ['B','S']:
            if len (spl) >= 3:
                sym = spl[2]
            else:
                continue
        elif command in ['X']:
            if len (spl) >= 2:
                sym = spl[1]
            else:
                continue
        else:
            sym = ''

        # Buy, Sell, or Split
        if command in ['B','S','X']:

            # date and time
            today = datetime.datetime.now()

            # Buy
            if command in ['B']:
                if (len(spl) != 4):
                    print ("\n\nNeed Buys to look like B <num> <sym> <price>.")
                    break
                num = spl[1]
                price = spl[3]

                buy_shares (sym, num, price, main_currency, lotorder, today, tmp_bcgtfile)

            # Sell or Split
            elif command in ['S','X']:

                for z in (range(len(slist))):
                    if (slist[z][3] == sym):
                        found = z
                        break

                if found == None:
                    print ("\n\nCan't find", sym)
                    continue

                # Sell
                if command in ['S']:

                    if (len(spl) != 5):
                       print ("\n\nNeed Sells to look like S <num> <sym> <price> <regfee>.")
                       continue

                    num = Decimal(spl[1])
                    sym = spl[2]
                    price = Decimal(spl[3])
                    regfee = Decimal(spl[4])
                    amt_val = newmoneyfmt(price * num)
                    #print ("Amt : ", amt_val)

                    sell_shares (slist, z, sym, num, price, main_currency, regfee, lotorder, today, tmp_bcgtfile)

                # Split
                elif command == 'X' and len(spl) == 5:
                     print ('\"Split', sym, num, 'FOR', splfor+'"')
                     print ('   Not written yet...')

                else:
                    print ("Missing something on Split?", spl)

        elif command in ['D']:
           done = True
        else:
           print ("What?")


    # post process any contents of tmp_bcgtfile to get bcgtfile
    tmp_bcgtfile.flush()
    tmp_bcgtfile.close()
    #os.system ("cat "+tmp_bcgtfile_name)
    os.system (postprocess)
    os.system(mk_bl_tmp)
    os.system (fix_output)
    os.system (move_output)
    os.system (cleanup_tmpfiles)
    
    print ("OUTPUT -->")
    os.system ("cat "+bcgtfile_name)
    print ("<--OUTPUT")

    # Export table if requested
    if args.output is not None:
        table[0][0] += ' ({:%Y-%m-%d %H:%M})'.format(datetime.datetime.now())
        write_table(table, args.output)

    return 0


if __name__ == '__main__':
    main()


