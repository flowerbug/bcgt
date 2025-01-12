

# Bcgt

A Beancount Tool to Generate Beancount Transactions for Stock Buys, Sells, Splits[*].

Bcgt is adapted from the export.py program referenced from beangrow which was available in earlier beancount versions, written by Martin Blais, with the following:

Copyright: "Copyright (C) 2018  Martin Blais"
License: "GNU GPLv2"

My changes are copyright to me flowerbug@anthive.com, but nothing I'm doing is very complicated.


# Introduction and Rationale

export.py was not working on beancount v2 or v3 but I removed some parts that were giving errors so I could get a usable result.  In no way is the output of bcgt meant to be compatible with what export.py produced, but there might be similarities.

I edited export.py to provide a list of lots of stock currently held.  Enter commands to Buy, Sell or Split[*].  What bcgt then does is generate beancount transactions that will get further processed by autobean-format (and since I am picky about how I like my transactions to look I use several options when running it).  These transactions are left in a file or you can cut and paste from the screen.  The main rationale for using this program is that it finds all of your current lots for you (so you don't have to search for them) and it also does the math and formatting.

What it DOES NOT do is append transactions to your existing beancount files, but you could change the program to put the file in your existing beancount transactions directory so it would be scanned.


# Two Short Examples

It is a very simple command line interface if you are familiar with the export.py program I have currently kept all the existing options and just added a few more.

To Buy 10 shares of ABT at 112.00 type in "B 10 ABT 112.00" generate the beancount transaction which will then get put into a temporary file.  To Sell you would type in "S 10 ABT 120.00 0.05" (the last number 0.05 is the fee the broker charges you which will be subtracted from your gains or added to your losses).

When Done type in D and the transactions are printed to the screen or you can get them from the file.


# Help Screen:

Here is the current help screen from running the command:

$python bcgt.py --help ledger.bc


usage: bcgt.py [-h] [-C CURRENCY] [-s] [-f] [-c OUTPUT_COMMODITIES]
               [-a OUTPUT_ACCOUNTS] [-p OUTPUT_PRICES] [-r OUTPUT_RATES]
               [-m OUTPUT_POSTINGS] [-o OUTPUT]
               filename

List Unsold Lots and Generate Buy, Sell and Split Transactions.

The primary purpose of this script is to generate Buy, Sell and Split
transactions.

The secondary purpose of this script is to:

- Produce a table of postings for the assets and liabilities
- Produce a table of per-account attributes
- Produce a table of per-commodity attributes
- Join these tables
- Output them to a CSV file.

Note: This version of the script has been modified to ignore some errors and
to not rearrange the order so it may no longer provide the same output as the
original version.


positional arguments:
  filename              Beancount input file

options:
  -h, --help            show this help message and exit
  -C CURRENCY, --currency CURRENCY
                        Override the default output currency (default is first
                        operating currency)
  -s, --switch-acct     Override the default account to REG (default is non-
                        taxable ROTH account)
  -f, --switch-lot-pref
                        Override the default lot sale selection order to
                        FIFO(default is LIFO)
  -c OUTPUT_COMMODITIES, --output_commodities OUTPUT_COMMODITIES
                        CSV filename to write out the commodities table to.
  -a OUTPUT_ACCOUNTS, --output_accounts OUTPUT_ACCOUNTS
                        CSV filename to write out the accounts table to.
  -p OUTPUT_PRICES, --output_prices OUTPUT_PRICES
                        CSV filename to write out the prices table to.
  -r OUTPUT_RATES, --output_rates OUTPUT_RATES
                        CSV filename to write out the rates table to.
  -m OUTPUT_POSTINGS, --output_postings OUTPUT_POSTINGS
                        CSV filename to write out the postings table to.
  -o OUTPUT, --output OUTPUT
                        CSV filename to write out the final joined table to.


# Lot Order, Different Accounts, Multiple Lots, Fees, Partial Lots, All Lots

The default Sell lot order is LIFO, but there is the switch -f to change that to FIFO.  The default account is a ROTH account but there is the switch -s to change that to REG.  All of these can be changed in the source code to fit your account preferences (along with the account to get funds from or to put funds into).

If you sell more shares than are in the first lot available this script will keep selling lots in the preferred order to fit your desires.  The fee is split proportionately among the different lots, but it may not be accurate in reflecting what the stock brokerage does, so it may really be best to sell only within one lot at a time (at least until I can find out what the formula actually is).  This code will also sell a part of a lot.  Or if you want to sell all of your shares you can put in a big number and it will sell all your lots and then stop when they're gone.


# About Lot labels

You can change it to whatever you like, but I use a combination of the stock symbol, the date and time down to the second.  If you need finer resolution than that you could add microseconds or a random string of some sort.

If you are generating Buy transactions around midnight the date will change.


# For The Moment in This Initial Version

I am not changing or adding to existing files at all.  To make actual changes reflect in what you see and can act upon in this script you have to generate the transaction, put it in your transaction files someplace and then rerun this script.  Yes, it is temporarily clunky, but that is the safe way to do things for the moment.  Instead I am appending to temporary files which then can be edited if needed before being added to the regular transaction files.


# What Am I Running This On

Debian GNU/Linux testing.

Dependencies: Python, autobean-format, beancount.

I also set up virtual environments in python to run beancount so the different dependencies don't clash with my existing python system versions.


# What about Split

[*] Split is not done yet.


