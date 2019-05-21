#!/usr/bin/python3
#
# TODO:
#   centring
#   bold, italic
#   tikz/includegraphics
#   tables

"""A script to convert lzl files to LaTeX files.

lzl (Lazy LaTeX) is a simple markup designed with two purposes in mind:
1. to reduce the amount you need to type into a LaTeX file,
2. to allow export to other formats such as HTML.
For a summary of lzl syntax, see the readme file.

Call it with

$ lzl.py filename tex [article|book|...]

or

$ lzl.py filename html

There are several global variables:

in_file:           this is the input lzl file specified as the first command line argument
out_file:          if in_file is "fooo.lzl" then out_file is "fooo.tex" (will later allow options like HTML)
mode:              html or tex (second command line argument); default is tex
doc_class:         this specifies the document class for LaTeX output (third, optional, command line argument); default is "article"
tab_length:        lzl is indented like Python; tab_length specifies the number of spaces per indent

tex_file:          a list which accumulates, line-by-line, the output to write
                   to out_file
open_environments: a list which keeps track of nested environments (e.g. we're
                   inside an itemize inside a claim inside a proof inside a document)

There are several functions:

count_tabs:        counts number of indents at the beginning of a line
is_item:           tests if a line represents a new item in an itemize
is_enum:           tests if a line represents a new item in an enumerate
make_line:         given a line of lzl, converts it to a line of LaTeX or HTML (called by write_body)
write_body:        handles a line (including opening/closing environments) 
                   (called by write_data whilst in the body of the document)
write_head:        handles a line of metadata
                   (called by write_data whilst in the head of the document)
write_data:        reads in_file line by line, parsing into LaTeX or HTML. Returns a list of lines to be written to out_file

The "main" program which runs when the program is called opens out_file and writes the output of write_data to it
"""

import sys
import subprocess

mode='tex'
doc_class='article'
in_file=sys.argv[1]
if len(sys.argv)>2:
    mode=sys.argv[2]
    if len(sys.argv)>3:
        doc_class=sys.argv[3]
tab_length=2
if mode=='tex':
    open_environments=['document']
    first_line=['\\documentclass{' + doc_class + '}']
    end_head_line=['\\begin{document}','\maketitle']
elif mode=='html':
    open_environments=['html']
    first_line=['<html>','<head>']
    end_head_line=['</head>','<body>']
    if doc_class=='blog':
        with open('./aux/headline') as headlines:
            for headline in headlines:
                end_head_line.append(headline)
out_file=in_file[:-3]+mode

def count_tabs(line):
    '''Each line starts with a certain amount of indentation. This should
    be a multiple of the basic unit "tab_length". This function
    recursively computes the number of tabs (i.e. number of multiples
    of tab_length) of whitespace appearing at the beginning of the
    given line.

    '''
    if line[0:tab_length].isspace():
        return 1+count_tabs(line[tab_length:])
    else:
        return 0

def is_item(token):
    return token=="-"

def is_enum(token):
    return token=="!"

def make_line(words):
    if words[0]=="#":
        # start new block environment
        open_environments.append(words[1])
        env_type=words[1]
        env_tex_label=''
        env_tex_text=''
        env_html_label=''
        env_html_text=''
        if len(words)>2:
            env_tex_label='\label{'+words[2]+'}'
            env_html_label=' id="'+words[2]+'" '
            if len(words)>3:
                env_tex_text='['+' '.join(words[3:])+']'
                env_html_text='('+' '.join(words[3:])+')'
        new_lines={'tex':['\\begin{'+words[1]+'}'+env_tex_text+env_tex_label],
                  'html':['<div class="'+words[1]+'"'+env_html_label+'>'+env_html_text+' ']}
    elif is_item(words[0]):
        # a new itemize must be started
        new_env={'tex':'itemize',
                 'html':'ul'}
        open_environments.append(new_env[mode])
        new_lines={'tex':['\\begin{itemize}','\item ' + ' '.join(words[1:])],
                   'html':['<ul>','<li>'+' '.join(words[1:])]}
    elif is_enum(words[0]):
        # a new enumerate must be started
        new_env={'tex':'enumerate',
                 'html':'ol'}
        open_environments.append(new_env[mode])
        new_lines={'tex':['\\begin{enumerate}','\item ' + ' '.join(words[1:])],
                   'html':['<ol>','<li>'+' '.join(words[1:])]}
    elif words[0]==''.join(['*' for i in range(0,len(words[0]))]):
        # start new section or chapter
        section_depth=len(words[0])
        new_lines={'html':['<h' + str(section_depth)+'>' + ' '.join(words[1:]) + \
                           '</h' + str(section_depth) + '>']}
        if doc_class in ['book','memoir']:
            if len(words[0])==1:
                # * chapter
                new_lines['tex']=['\chapter{' + ' '.join(words[1:]) + '}']
            else:
                # ** section
                # *** subsection...
                new_lines['tex']=['\\' + ''.join(['sub' for i in words[0][:-2]]) + \
                                  'section{' + ' '.join(words[1:])+'}']
        else:
            # * section
            # ** subsection...
            new_lines['tex']=['\\' + ''.join(['sub' for i in words[0][:-1]]) + \
                              'section{' + ' '.join(words[1:])+'}']
    else:
        new_lines={'tex':[' '.join(words)],
                   'html':[' '.join(words)]}
    return new_lines[mode]

def write_head(words):
    if mode=='tex' and (words[0]=='@' or words[0]=='@tex'):
        return ['\\'+words[1]+'{'+' '.join(words[2:])+'}']
    elif mode=='html' and (words[0]=='@' or words[0]=='@html'):
        if words[1]=='title':
            return ['<'+words[1]+'>'+' '.join(words[2:])+'</'+words[1]+'>']
        elif words[1] in ['author','description','keywords']:
            return ['<meta name="'+words[1]+'" content="'+' '.join(words[2:])+'"/>']
        elif words[1]=='include':
            with open(words[2]) as g:
                return g.read().splitlines()
    else:
        return []    

def write_body(words,new_depth,current_depth):
    if not words: # handle empty lines
        if mode=='html':
            return ['<p>\n']
        else:
            return ['\n']
    else:
        if new_depth<current_depth: # if we have excess environments open...
            # close all but the last excess environment
            new_lines={'tex':[],
                       'html':[]}
            for i in range(0,current_depth-new_depth-1):
                closing=open_environments.pop()
                new_lines['tex']+=['\end{'+closing+'}']
                if closing in ['ul','ol']:
                    new_lines['html']+=['</'+closing+'>']
                else:
                    new_lines['html']+=['</div>']
            current_environment=open_environments[-1]
            # The last excess environment could be an
            # itemize/enumerate and we might be adding an
            # item...
            if current_environment in ['itemize','ul'] and is_item(words[0]):
                new_lines['tex']+=['\item ' + ' '.join(words[1:])]
                new_lines['html']+=['<li>' + ' '.join(words[1:])]
                return new_lines[mode]
            elif current_environment in ['enumerate','ol'] and is_enum(words[0]):
                new_lines['tex']+=['\item ' + ' '.join(words[1:])]
                new_lines['html']+=['<li>' + ' '.join(words[1:])]
                return new_lines[mode]
            else:
                # ...otherwise, close it, convert the line into
                # LaTeX/HTML and return the result
                closing=open_environments.pop()                
                new_lines['tex']+=['\end{'+closing+'}']
                if closing in ['ul','ol']:
                    new_lines['html']+=['</'+closing+'>']
                else:
                    new_lines['html']+=['</div>']
                return new_lines[mode]+make_line(words)
        else:
            # If we don't have to worry about closing environments,
            # just convert the line into LaTeX and write to tex_file
            return make_line(words)
        
def handle_hyperlinks():
    output=[]
    raw_file=[]
    parsed_file=[]
    with open(in_file) as f:
        for line in f:
            if mode != 'html':
                output+=[line]
            else:
                for char in line:
                    raw_file+=[char]

    if mode != 'html':
        return output
    
    flag=0
    for char in raw_file:
        if flag == 0 and char != '[':
            parsed_file+=[char]
        elif flag == 0 and char == '[':
            flag = 1    # There may be a link about to start...
            parsed_file+=[char]
        elif flag == 1 and char != '[':
            flag = 0    # Ach! False alarm
            parsed_file+=[char]
        elif flag == 1 and char == '[':
            flag = 2    # Link has started
            parsed_file.pop()
            parsed_file.extend(list('<a href="'))
        elif flag == 2 and char != ']':
            parsed_file+=[char] # Inside link
        elif flag == 2 and char == ']':
            parsed_file.extend(list('">'))
            flag = 3 # Passing into link text
        elif flag == 3 and char == '[':
            flag = 4
        elif flag == 4 and char != ']':
            parsed_file+=[char] # Inside link text
        elif flag == 4 and char == ']':
            flag = 5 # Link text has passed
        elif flag == 5 and char == ']':
            flag = 6 # Whole link has passed
            parsed_file.extend('</a>')
            flag = 0

    return ''.join(parsed_file).splitlines(True)

def handle_tikz(lzlist):
    if mode=='tex':
        return lzlist
    elif mode=='html':
        tikzmode=0
        img_index=-1
        imgs=[]
        output=[]
        current_depth=0
        for line in lzlist:
            if tikzmode==0:
                if line.split()[0:2]==['#','tikzpicture']:
                    current_depth=count_tabs(line)
                    tikzmode=1
                    img_index+=1
                    img_init=['\documentclass[tikz]{standalone}',
                                 #'\include{tikzhead}',
                                 '\\begin{document}',
                                 '\\begin{tikzpicture}']
                    if len(line.split())>=2:
                        img_init.extend(line.split()[2:])
                    imgs.append(img_init)
                else:
                    output.append(line)
            else:
                if count_tabs(line)<=current_depth:
                    imgs[img_index].extend(['\end{tikzpicture}',
                                            '\end{document}'])
                    out_line=''.join([' ' for spaces in range(0,current_depth*tab_length)])+\
                              '<center><img src="./img/'+in_file[:-4]+\
                              str(img_index)+'.jpg"/></center>'
                    output.extend([out_line,line])
                    tikzmode=0
                else:
                    if line.split():
                        imgs[img_index].append(line.strip())
        if tikzmode==1:
            imgs[img_index].extend(['\end{tikzpicture}',
                                    '\end{document}'])
            out_line='<img src="./img/'+in_file[:-4]+str(img_index)+'.jpg"/>'
            output.extend([out_line])

        for img in imgs:
            img_root=in_file[:-4]+str(imgs.index(img))
            img_file=img_root+'.tex'
            destination_pdf=img_root+'.pdf'
            destination_jpg='./img/'+img_root
            with open(img_file,'w') as f:
                for tikz in img:
                    f.write("%s\n" % tikz)
            subprocess.run(["pdflatex",img_file,destination_pdf])
            subprocess.run(["pdftocairo","-singlefile","-jpeg",destination_pdf,destination_jpg])
        return output
                
def write_data(data,parsed_output):
    in_header=True
    for line in parsed_output:
        if in_header:
            if line[0]=='@':
                data+=write_head(line.split())
            else:
                in_header=False
                if mode=='html':
                    open_environments.append('body')
                data+=end_head_line
        else:
            # number of environments which are open
            current_depth=len(open_environments)
            always_open={'tex':1, # always in 'document'
                         'html':2} # always in 'html','body'
            # number of environments which _should_ be open:
            new_depth=count_tabs(line)+always_open[mode]
            data+=write_body(line.split(),new_depth,current_depth)

    # Once we reach the end of the document, close all open
    # environments
    for i in range(0,len(open_environments)):
        closing=open_environments.pop()
        new_lines={'tex':['\end{'+closing+'}']}
        if closing in ['ul','ol','html']:
            new_lines['html']=['</'+closing+'>']
        elif closing in ['body']:
            new_lines['html']=[]
            if doc_class=='blog':
                with open('./aux/endline') as endlines:
                    for endline in endlines:
                        new_lines['html'].append(endline)
            new_lines['html'].append('</'+closing+'>')
        else:
            new_lines['html']=['</div>']
        data+=new_lines[mode]
    return data
    

with open(out_file, 'w') as f:
    for item in write_data(first_line,handle_tikz(handle_hyperlinks())):
        f.write("%s\n" % item)

if mode=='tex':
    subprocess.run(["pdflatex",out_file])
