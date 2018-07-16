# latex

``latex`` is a python script that prints statistics on latex projects. In addition to the script itself, I wrote a client.py and a server.py. By this, the script can easily be integrated into an automated build process, e.g. to show errors after each build.

When client.py is invoked without argument, it opens up a new shell. Using ``help`` lists available commands.

## installation

I implemented this using anaconda v.1.6.5 with python 3.6.3. No other environments have been tested. 

Additionally installed python modules are:
* cmd
* pickle
* colorama 
* argparse

## known limitations

One of the intentions for printing the toc has been to see the number of words written in each section. For counting the words, each section requires to be in it's own file. In addition to that, word count is not very accurate. Things like figures and equations are skipped but on top of that everthing delimited by whitespaces is interpreted as a word.

When backup is used, toc shows the number of newly written words (compared to the last backup). For my purpose, a backup is simply generated when the latex build process is initiated for the first time (on a given day). I did not consider further improvements here. When a backup is given and the structure of the project is changed (i.e. sections are removed), ``DiffTree`` (see latex.py line 432) throws key errors since sections are missing. I did not bother fixing that as had no use for handling this situation.
