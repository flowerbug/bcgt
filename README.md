

# Bcgt

A Beancount Tool to Generate Beancount Transactions for Stock Buys, Sells, Splits.

Bcgt is adapted from the export.py program referenced from beangrow which was available in earlier beancount versions, written by Martin Blais, with the following:

Copyright: "Copyright (C) 2018  Martin Blais"
License: "GNU GPLv2"

My changes are copyright to flowerbug@anthive.com, but nothing I'm doing is very complicated.


# Latest News For v2.3.2, Added Backdate and Tag Options

Please use the current version (v2.3.2) and report any issues that are not noted below.

The -b "backdate" and -t tag options are useful for when you've missed a day or want to use the actual Buy execution time or an approximate time when the Buy happened.  More details are included below.


# Introduction and Rationale

export.py was not working on beancount v2 or v3 but I removed some parts that were giving errors so I could get a usable result.  In no way is the output of bcgt meant to be compatible with what export.py produced, but there might be similarities.

I edited export.py to provide a list of lots of stock currently held.  Enter commands to Buy, Sell or Split.  What bcgt then does is generate beancount transactions that will get further processed by autobean-format (and since I am picky about how I like my transactions to look I use several options when running it).  These transactions are printed to the terminal and they are also placed into a file in either a default location or one you specify via the --dest parameter.  The main rationale for using this program is that it finds all of your current lots for you (so you don't have to search for them) and it also does the math and formatting.

After making any change all the files will be rescanned and the list will be redisplayed.


# Three Short Examples

It is a very simple command line interface if you are familiar with the export.py program I have currently kept all the existing options and just added a few more.

To Buy 10 shares of ABT at 112.00 type in "B 10 ABT 112.00" to generate the beancount transaction which will then get put into a temporary file.  To Sell you would type in "S 10 ABT 120.00 0.05" (the last number 0.05 is the fee the broker charges you which will be subtracted from your gains or added to your losses).  To Split you would type in "X ABT 2 FOR 1".

When Done type in D.


# Help Screen:

<pre>
$ python bcgt.py --help ledger.bc

usage: bcgt.py [-h] [-dest DESTINATION] [-C CURRENCY] [-s] [-f]
               [-c OUTPUT_COMMODITIES] [-a OUTPUT_ACCOUNTS] [-p OUTPUT_PRICES]
               [-r OUTPUT_RATES] [-m OUTPUT_POSTINGS] [-o OUTPUT]
               filename

List Unsold Lots and Generate Buy, Sell and Split Transactions.

The primary purpose of this script is to generate Buy, Sell and Split
beancount transactions.  If a destination path and file name is supplied
the results will be appended to that location (the path and directory
must already exist) otherwise a default location will be used.

The secondary purpose of this script is to:
- Produce a table of postings for the assets and liabilities
- Produce a table of per-account attributes
- Produce a table of per-commodity attributes
- Join these tables
- Output them to a CSV file.

  Each of these can be output to a file.


Note: This version of the script has been modified to ignore some errors
and to not rearrange the order so it may no longer provide the same
output as the original version.


positional arguments:

  filename              Beancount input file


options:

  -h, --help            show this help message and exit
  -dest DESTINATION, --destination DESTINATION
                        Destination of generated transactions
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
</pre>


# Lot Order, Different Accounts, Multiple Lots, Fees, Partial Lots, All Lots

The default Sell lot order is LIFO, but there is the switch -f to change that to FIFO.  The default account is a ROTH account but there is the switch -s to change that to REG.  All of these can be changed in the source code to fit your account preferences (along with the account to get funds from or to put funds into).

If you sell more shares than are in the first lot available this program will keep selling lots in the preferred order to fit your desires.  The fee is split proportionately among the different lots, but it may not be accurate in reflecting what the stock brokerage shows, so it may really be best to sell only within one lot at a time (at least until I can find out what the formula actually is - I've only had the fees given to me as a single amount per chunk of shares sold, but there is no mention of which lot is being sold other than my own records and looking at the PnL history - they certainly are not as clear as I am in my records).  This code will also sell a part of a lot.  Or if you want to sell all of your shares you can put in a big number and it will sell all your lots and then stop when they're gone.


# About Lot labels

You can change it to whatever you like, but I use a combination of the stock symbol, the date and time down to the second.  If you need finer resolution than that you could change the code to add microseconds or a string of some sort, but remember that the lot order is sorted by LIFO or FIFO.

If you are generating Buy transactions around midnight the date of the transaction and the lot label will change.  If you want more control over the date and time for Buys use the -b "backdate" and -t tag options.


# The Destination Path and File

With the 1.0.0 version you can specify a location to append the transactions by using the --dest option on the command line and as a part of that specification include the path and filename.  As an example:

$ python bcgt.py --dest tree/Assets/SB/SCH/latest.bc ledger.bc

The ledger.bc supplied in this release will pick up ANY added files with the .bc extension in the tree/Assets/SB/SCH directory.

By default I am not changing or adding to existing files in the account hierarchy other than the default path and file.  Once you are satisfied that the latest transactions are correct you can move them to other files.  I recommend this cautious and examined approach along with regular backups.  I do not recommend using any other destination.  Please make backups and test before risking a lot of work.  And if you do mess things up even after being warned - it isn't my fault.  So far I have not noticed anything odd happening.

What about /dev/null?  Sure!  If you want to take the output from the screen and don't want any transactions put anyplace else.  Just use:

$ python bcgt.py --dest /dev/null ledger.bc

As usual you would need to have permission to access and to append to any destination file.  I currently don't do any error checking on the destination.


# What Am I Running This On

Debian GNU/Linux testing.

Dependencies: Python, autobean-format, beancount.

I also set up virtual environments in python to run beancount so the different dependencies don't clash with my existing python system versions.


# What About Split?

Split now works.


# When Selling the Fee Amount is Optional

- If you are entering a lot of sell transactions that do not have a fee you can leave the zero amount off the end and it will be entered for you as zero.  Do not be upset at seeing a negative zero in your transaction - it is a valid python Decimal value and I like having that there to remind me that the value should be negative if it is there at all.


# The Backdate and Tag Options

The commands entry prompt now looks like:

<pre>
(B)Buy, (S)Sell, (X)Split or (D)one
Enter: 'B <num> <sym> <price> [[-b "backdate" -t tag]|[-t tag]]' or 'S <num> <sym> <price> [<regfee>] [-b "backdate"]' or 'X <sym> <anum> FOR <bnum> [-b "backdate"]' or 'D'
</pre>

Backdate: The -b option lets you specify a day or use any phrase that dateparser.parse will recognise, so words like "yesterday", "today" or "tomorrow" will work along with phrases like "last monday" should also work.  Because the phrases can be more than one word you need to use matching quotes around them.  I'm not really sure how well this will work if used for future dates - at present I'm mostly using this option in case I've not put in a trade on a certain day and am getting caught up within a few days.

Tag:  The -t option.  Along with -b you can use the -t option to specify the time (as one single item in HHMMSS format) but you can also make up your own tags to use instead of the time as long as it is a single item without any strange characters mixed in.  This value will be used as part of the label and sorted so you will need to be sure that you use it in a consistent manner with whatever lot selling setting you have on your account.  Using -t alone to specify the time is nice if you want to keep track of your trade execution time as some trading platforms do provide that information.


# Notes, Errors And Breaking Changes

You should be using the most current version.

If you are doing something strange test it out first to make sure you get what you expect - like for example some of the phrases I expect the date parser to know about are not recognized but quite a few are.  I've found that most of the phrases I'm using are "yesterday" or "last <day>" where <day> is the day of the week.

Input is converted to upper case and error checking on the format is very simplistic.  Adding the -b and -t options on top of the optional fee amount meant I had to redo all the logic for command input parsing and I have not completely tested every possible combination of dates and time and the various phrases that the date parser will accept.

Also, I did notice that there is some strange things going on with transactions dated into the future so I personally avoid doing those until I figure out if it is a bug or just a normal feature of beancount.  At present I don't recommend doing transactions dated into the future and I also have not extensively tested transactions that are backdated and mixed in with other existing transactions.  Mostly I use backdate and tag if I've missed getting transactions entered on the day I made them or I want to record an actual time on the current day's transactions.

If you accidentally type in something that isn't a number where it should be you will get some rather unhelpful error messages - I need to improve that.

If you buy a stock today you can't split it until tomorrow as beancount doesn't use time yet for all transactions.  I don't think you can do this in real trading anyways since the stock does not settle the same day.  If you do buy a stock and want to split it your buy should be backdated using the -b option to the day when you really did buy it - then a split applied on the current day or backdated to the day after you bought it should work.

I have not had to add any new commodities/symbols to the commodities.bc file, but at some point I hope to make that work automatically.  I usually edit prices.bc to add new symbols, but I also hope to get that to happen automatically.

Currently no error checking is done on the destination location or file or permissions.

No errors or issues I'm aware of other than those I've noted here or up above.

