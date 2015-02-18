#!/usr/bin/env python

# @file:    dumpSG.py
# @purpose: read a ROOT file containing xAOD Objects and dump the contents
# @author:  Giordon Stark <gstark@cern.ch>
# @date:    November 2014
#
# @example:
# @code
# printSGDetails.py aod.pool.root
# printSGDetails.py aod.pool.root --interactive
# printSGDetails.py aod.pool.root --help
# @endcode
#

# __future__ imports must occur at beginning of file
# redirect python output using the newer print function with file description
#   print(string, f=fd)
from __future__ import print_function
# used to redirect ROOT output
#   see http://stackoverflow.com/questions/21541238/get-ipython-doesnt-work-in-a-startup-script-for-ipython-ipython-notebook
import tempfile

import os, sys
# grab the stdout and have python write to this instead
# ROOT will write to the original stdout
STDOUT = os.fdopen(os.dup(sys.stdout.fileno()), 'w')

# for logging, set it up
import logging
root_logger = logging.getLogger()
root_logger.addHandler(logging.StreamHandler(STDOUT))
dumpSG_logger = logging.getLogger("dumpSG")

# First check if ROOTCOREDIR exists, implies ROOTCORE is set up
try:
  os.environ['ROOTCOREDIR']
except KeyError:
  raise OSError("It appears RootCore is not set up. Please set up RootCore and then try running me again. Hint: try running `rcSetup`")

# import all libraries
import argparse

# defaultdict is useful for parsing the file
from collections import defaultdict

# use regular expressions to filter everything down
import re

# used to build a copy of original dictionary
import copy

# used for the filtering of objects
import fnmatch

# used for output formats
import json
try:
  import cPickle as pickle
except:
  import pickle

'''
  with tempfile.NamedTemporaryFile() as tmpFile:
    if not args.root_verbose:
      ROOT.gSystem.RedirectOutput(tmpFile.name, "w")

    # execute code here  

    if not args.root_verbose:
      ROOT.gROOT.ProcessLine("gSystem->RedirectOutput(0);")
'''

# Set up ROOT
import ROOT

def format_arg_value(arg_val):
  """ Return a string representing a (name, value) pair.
  
  >>> format_arg_value(('x', (1, 2, 3)))
  'x=(1, 2, 3)'
  """
  arg, val = arg_val
  return "%s=%r" % (arg, val)

# http://wordaligned.org/articles/echo
def echo(*echoargs, **echokwargs):
  dumpSG_logger.debug(echoargs)
  dumpSG_logger.debug(echokwargs)
  def echo_wrap(fn):
    """ Echo calls to a function.
    
    Returns a decorated version of the input function which "echoes" calls
    made to it by writing out the function's name and the arguments it was
    called with.
    """

    # Unpack function's arg count, arg names, arg defaults
    code = fn.func_code
    argcount = code.co_argcount
    argnames = code.co_varnames[:argcount]
    fn_defaults = fn.func_defaults or list()
    argdefs = dict(zip(argnames[-len(fn_defaults):], fn_defaults))

    def wrapped(*v, **k):
      # Collect function arguments by chaining together positional,
      # defaulted, extra positional and keyword arguments.
      positional = map(format_arg_value, zip(argnames, v))
      defaulted = [format_arg_value((a, argdefs[a]))
                   for a in argnames[len(v):] if a not in k]
      nameless = map(repr, v[argcount:])
      keyword = map(format_arg_value, k.items())
      args = positional + defaulted + nameless + keyword
      write("%s(%s)\n" % (fn.__name__, ", ".join(args)))
      return fn(*v, **k)
    return wrapped

  write = echokwargs.get('write', sys.stdout.write)
  if len(echoargs) == 1 and callable(echoargs[0]):
    return echo_wrap(echoargs[0])
  return echo_wrap

@echo(write=dumpSG_logger.debug)
def inspect_tree(t):
  '''
  filter based on the 4 elements:
    - Container Name: this comes in the form like `AntiKt10LCTopo`
      - this contains the correct type for the object (xAOD::JetContainer_v1)
    - AuxContainer Name: this comes in the form like `AntiKt10LCTopoAux.`
      - this contains the DataVector<xAOD::Jet> type, which is very confusing and useless for us
      - **NB: I currently do nothing with it, but I left it in for future development if we need it
    - Container Property: this comes in the form like `AntiKt10LCTopoAux.pt`
      - this contains vector<type> type, which is filtered to become `type` via xAOD_Type_Name
    - Container Attribute: this comes in the form like `AntiKt10LCTopoAuxDyn.Tau1`
      - this contains vector<type> type, which is filtered to become `type` via xAOD_Type_Name
  '''

  # list of properties and methods given Container Name
  xAOD_Objects = defaultdict(lambda: {'prop': [], 'attr': [], 'type': None, 'has_aux': False, 'rootname': None})  

  # lots of regex to pass things around and figure out structure
  xAOD_Container_Name = re.compile('^([^:]*)(?<!\.)$')
  xAOD_AuxContainer_Name = re.compile('(.*)Aux\.$')
  xAOD_Container_Prop = re.compile('(.*)Aux\.([^:]+)$')
  xAOD_Container_Attr = re.compile('(.*)AuxDyn\.([^:]+)$')
  xAOD_Type_Name = re.compile('^(vector<)?(.+?)(?(1)(?: ?>))$')
  xAOD_remove_version = re.compile('_v\d+')
  xAOD_Grab_Inner_Type = re.compile('<([^<>]*)>')

  # call them elements, because there are 4 types inside the leaves
  elements = t.GetListOfLeaves()
  for el in elements:
    # get the name of the element
    # because of stupid people, we need to go up to the branch for this
    elName = el.GetBranch().GetName()

    # filter its type out
    elType = el.GetTypeName()
    elType = xAOD_remove_version.sub('', xAOD_Type_Name.search(elType).groups()[1].replace('Aux','') )

    # match the name against the 4 elements we care about, figure out which one it is next
    m_cont_name = xAOD_Container_Name.search(elName)
    m_aux_name = xAOD_AuxContainer_Name.search(elName)
    m_cont_prop = xAOD_Container_Prop.search(elName)
    m_cont_attr = xAOD_Container_Attr.search(elName)

    # set the type
    if m_aux_name:
      container, = m_aux_name.groups()
      xAOD_Objects[container]['type'] = elType
      xAOD_Objects[container]['has_aux'] = True  # we found the aux for it
      xAOD_Objects[container]['rootname'] = elName
    # set the property
    elif m_cont_prop:
      container, property = m_cont_prop.groups()
      xAOD_Objects[container]['prop'].append({'name': property, 'type': elType, 'rootname': elName})
    # set the attribute
    elif m_cont_attr:
      container, attribute = m_cont_attr.groups()
      if 'btagging' in attribute.lower():
        # print attribute, "|", elName, "|", elType
        ''' 
        David found an issue where instead of expecting something that looks like
            btaggingLink | AntiKt10LCTopoJetsAuxDyn.btaggingLink | ElementLink<DataVector<xAOD::BTagging> >
        it instead looks like
            btaggingLink_ | AntiKt10LCTopoJetsAuxDyn.btaggingLink_ | Int_t
        '''
        btaggingType = xAOD_Grab_Inner_Type.search(elType)
        if btaggingType:
          elType = btaggingType.groups()[0] + ' *'
        attribute = attribute.replace('Link','')
        xAOD_Objects[container]['prop'].append({'name': attribute, 'type': elType, 'rootname': elName})
      else:
        xAOD_Objects[container]['attr'].append({'name': attribute, 'type': elType, 'rootname': elName})
    elif m_cont_name:
      # initialize with defaults if not set already
      container, = m_cont_name.groups()
      xAOD_Objects[container]['type'] = xAOD_Objects[container]['type'] or elType
      xAOD_Objects[container]['rootname'] = xAOD_Objects[container]['rootname'] or elName
 
  return xAOD_Objects

@echo(write=dumpSG_logger.debug)
def save_plot(pathToImage, item, container, width=700, height=500, formats=['png'], logTolerance=5.e2):
  c = ROOT.TCanvas(item['name'], item['name'], 200, 10, width, height)
  t.Draw(item['rootname'])

  # get histogram drawn and grab details
  htemp = c.GetPrimitive("htemp")
  # if it didn't draw a histogram, there was an error drawing it
  if htemp == None:
    entries, mean, rms =  0, 0.0, 0.0
    drawable = False
    counts_min, counts_max = 0.0, 0.0
  else:
    # we didn't have an error drawing it, let's apply makeup
    entries, mean, rms =  htemp.GetEntries(), htemp.GetMean(), htemp.GetRMS()
    # note that the absolute minimum is X > 0 [so 1 is the minimum value we obtain]
    #   this fixes the divide-by-zero error we would get
    counts_min, counts_max = htemp.GetMinimum(0), htemp.GetMaximum()
    drawable = True

    # set up the labeling correctly
    htemp.SetTitle(item['name'])
    htemp.SetXTitle(item['name'])

    # set log scale if htemp is drawable and the maximum/minimum is greater than tolerance
    if bool(counts_max/counts_min > logTolerance):
      dumpSG_logger.info("Tolerance exceeded for {0}. Switching to log scale.".format(item['name']))
    c.SetLogy(bool(counts_max/counts_min > logTolerance))
    
    #color the fill of the canvas based on various issues
    if entries == 0:
      c.SetFillColor(getattr(ROOT, args.no_entries))
    elif mean != 0 and rms == 0:
      c.SetFillColor(getattr(ROOT, args.no_rms))
    elif mean == 0:
      c.SetFillColor(getattr(ROOT, args.no_mean))
    else:
      c.SetFillColor(0)

    # no issues with drawing it
    c.Update()  # why need this?
    c.Modified()  # or this???
    c.Print(pathToImage, 'Title:{0}'.format(item['name']))
  del c

  item['entries'] = entries
  item['mean'] = mean
  item['rms'] = rms
  item['drawable'] = drawable
  item['counts'] = {}
  item['counts']['min'] = counts_min
  item['counts']['max'] = counts_max

  if drawable:
    # let the user know that this has RMS=0 and may be of interest
    if rms == 0:
      dumpSG_logger.warning("{0}/{1} might be problematic (RMS=0)".format(container, item['name']))
      dumpSG_logger.info("\tpath:\t\t{0}\n\tmean:\t\t{1}\n\trms:\t\t{2}\n\tentries:\t{3}".format(item['rootname'], item['mean'], item['rms'], item['entries']))
  else:
    errString = "{0}/{1} {{0}}".format(container, item['name'])
    detailErrString = "\tpath:\t\t{0}".format(item['rootname'])
    if 'ElementLink' in item['type']:
      # this is an example of what we can't draw normally
      dumpSG_logger.info(errString.format("is an ElementLink type"))
      dumpSG_logger.info(detailErrString)
    elif t.GetBranch(item['rootname']).GetListOfLeaves()[0].GetValue(0) == 0:
      # this is when the values are missing, but Leaf.GetValue(0) returns 0.0
      #     not sure why, ask someone what the hell is going on
      dumpSG_logger.warning(errString.format("has missing values"))
      dumpSG_logger.info(detailErrString)
    else:
      dumpSG_logger.warning(errString.format("couldn't be drawn"))
      dumpSG_logger.info(detailErrString)

@echo(write=dumpSG_logger.debug)
def make_report(t, xAOD_Objects, directory="report", merge_report=False):
  for container, items in xAOD_Objects.iteritems():
    # first start by making the report directory
    if not os.path.exists(directory):
      os.makedirs(directory)

    # check if we want to merge
    if merge_report:
      # we do, so pathToImage is directory/container.pdf
      pathToImage = os.path.join(directory, '{0}.pdf'.format(container))
      # https://root.cern.ch/root/HowtoPS.html
      # create a blank canvas for initializing the pdf
      blankCanvas = ROOT.TCanvas()
      blankCanvas.Print('{0}['.format(pathToImage))
    else:
      # we don't so pathToImage is directory/container/item['name'].pdf
      sub_directory = os.path.join(directory, container) 
      if not os.path.exists(sub_directory):
        os.makedirs(sub_directory)

    for item in items.get('prop', []) + items.get('attr', []):
      if not merge_report:
        # if we aren't merging, the path to image is based on item['name']
        pathToImage = os.path.join(sub_directory, '{0}.pdf'.format(item['name']))

      save_plot(pathToImage, item, container)

    if merge_report:
      # finalize the pdf, note -- due to a bug, you need to close with the last title
      #     even though it was written inside save_plot() otherwise, it won't save right
      blankCanvas.Print('{0}]'.format(pathToImage), 'Title:{0}'.format(item['name']))
      del blankCanvas

  with open(os.path.join(directory, "info.json"), 'w+') as f:
    f.write(json.dumps(xAOD_Objects, sort_keys=True, indent=4))

  return True

@echo(write=dumpSG_logger.debug)
def filter_xAOD_objects(xAOD_Objects, args):
  p_container_name = re.compile(fnmatch.translate(args.container_name_regex))
  p_container_type = re.compile(fnmatch.translate(args.container_type_regex))

  # Python Level: EXPERT MODE
  filtered_xAOD_Objects = {k:{prop:val for prop, val in v.iteritems() if (args.list_properties and prop=='prop') or (args.list_attributes and prop=='attr') or prop in ['type','has_aux','rootname']} for (k,v) in xAOD_Objects.iteritems() if p_container_name.match(k) and p_container_type.match(v['type']) and (not args.has_aux or v['has_aux']) }
  return filtered_xAOD_Objects

@echo(write=dumpSG_logger.debug)
def dump_pretty(xAOD_Objects, f):
  currContainerType = ''
  # loop over all containers, sort by type
  for ContainerName, Elements in sorted(xAOD_Objects.items(), key=lambda (k,v): (v['type'].lower(), k.lower())):
    # print container type if we switch, or start
    if not currContainerType == Elements['type']:
      # check if it is not the start
      if not currContainerType == '':
        f.write('  %s\n\n' % ('-'*20))
      f.write('http://atlas-computing.web.cern.ch/atlas-computing/links/nightlyDocDirectory/%s/html/\n' % Elements['type'].replace(':','').replace('Container',''))
      f.write('%s\n' % Elements['type'])
      currContainerType = Elements['type']

    f.write('  |\t%s* %s\n' % (Elements['type'], ContainerName))

    if args.list_properties:
      for prop in sorted(Elements['prop'], key=lambda k: k['name'].lower()):
        f.write('  |\t  |\t%s &->%s()\n' % (prop['type'], prop['name']))
    if args.list_attributes:
      for attr in sorted(Elements['attr'], key=lambda k: k['name'].lower()):
        f.write('  |\t  |\t&->getAttribute<%s>("%s")\n' % (attr['type'], attr['name']))
    # this is to add a closing line on the secondary level if we're outputting one of props/attrs
    # NB: we should only add this if there are properties or attributes to print out
    if (args.list_attributes and len(Elements['attr']) > 0) or (args.list_properties and len(Elements['prop']) > 0):
      f.write('  |\t  %s\n  |\n' % ('-'*20))

  f.write('  %s\n' % ('-'*20))

@echo(write=dumpSG_logger.debug)
def dump_xAOD_objects(xAOD_Objects, args):
  # dumps object information given the structure output by inspect_tree()
  # NB: all sorting is done using lowercased strings because it's human-sorting
  with open(args.output_filename, 'w+') as f:
    if args.output_format == 'pretty':
      dump_pretty(xAOD_Objects, f)
    elif args.output_format == 'json':
      f.write(json.dumps(xAOD_Objects, sort_keys=True, indent=4))
    elif args.output_format == 'pickle':
      pickle.dump(xAOD_Objects, f)
    else:
      raise ValueError('args.output_format was not valid!')
  return True

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Process xAOD File and Dump Information.', usage='%(prog)s filename [filename] [options]')
  # positional argument, require the first argument to be the input filename
  parser.add_argument('input_filename',
                      type=str,
                      nargs='+',
                      help='input root file(s) to read')
  # these are options allowing for various additional configurations in filtering container and types to dump
  parser.add_argument('--tree',
                      type=str,
                      required=False,
                      dest='tree_name',
                      help='Specify the tree that contains the StoreGate structure. Default: CollectionTree',
                      default='CollectionTree')
  parser.add_argument('-o',
                      '--output',
                      type=str,
                      required=False,
                      dest='output_filename',
                      help='Output file to store dumped information. Default: info.dump',
                      default='info.dump')
  parser.add_argument('-d',
                      '--output_directory',
                      type=str,
                      required=False,
                      dest='output_directory',
                      help='Output directory to store the report generated. Default: report',
                      default='report')
  parser.add_argument('-t',
                      '--type',
                      type=str,
                      required=False,
                      dest='container_type_regex',
                      help='Regex specification for the xAOD container type. For example, --type="xAOD::Jet*" will match `xAOD::JetContainer` while --type="xAOD::*Jet*" will match `xAOD::TauJetContainer`. This uses Unix filename matching. Default: *',
                      default='*')
  parser.add_argument('-c',
                      '--container',
                      type=str,
                      required=False,
                      dest='container_name_regex',
                      help='Regex specification for the xAOD container name. For example, --container="AntiKt10LCTopo*" will match `AntiKt10LCTopoJets`. This uses Unix filename matching. Default: *',
                      default='*')
  parser.add_argument('-f',
                      '--format',
                      type=str,
                      required=False,
                      dest='output_format',
                      choices=['json','pickle','pretty'],
                      help='Specify the output format. Default: pretty',
                      default='pretty')
  parser.add_argument('-v',
                      '--verbose',
                      dest='verbose',
                      action='count',
                      default=0,
                      help='Enable verbose output of various levels. Use --debug-root to enable ROOT debugging. Default: no verbosity')
  parser.add_argument('--debug-root',
                      dest='root_verbose',
                      action='store_true',
                      help='Enable ROOT debugging/output. Default: disabled')
  parser.add_argument('-b',
                      '--batch',
                      dest='batch_mode',
                      action='store_true',
                      help='Enable batch mode for ROOT. Default: disabled')
  parser.add_argument('--has_aux',
                      dest='has_aux',
                      action='store_true',
                      help='Enable to only include containers which have an auxillary container. By default, it includes all containers it can find. Default: disabled')
  parser.add_argument('--prop',
                      dest='list_properties',
                      action='store_true',
                      help='Enable to print properties of container. By default, it only prints the xAOD::ContainerType and containers for that given type. This is like an increased verbosity option for container properties. Default: disabled')
  parser.add_argument('--attr',
                      dest='list_attributes',
                      action='store_true',
                      help='Enable to print attributes of container. By default, it only prints the xAOD::ContainerType and containers for that given type. This is like an increased verbosity option for container attributes. Default: disabled')
  parser.add_argument('--report',
                      dest='make_report',
                      action='store_true',
                      help='Enable to also create a directory containing plots and generate additional reporting information/statistics. By default, this is turned off as it can be potentially slow. The output directory containing the plots will be named `xAODDumper_Report`. Default: disabled')
  parser.add_argument('--merge-report',
                      dest='merge_report',
                      action='store_true',
                      help='Enable to merge the generated report by container. By default, this is turned off. Default: disabled')

  # arguments for report coloring
  parser.add_argument('--noEntries',
                      type=str,
                      required=False,
                      dest='no_entries',
                      help='If a plot generated by a report has no entries, color it with this ROOT color value. Default: kRed',
                      default='kRed')
  parser.add_argument('--noRMS',
                      type=str,
                      required=False,
                      dest='no_rms',
                      help='If a plot generated by a report has RMS = 0.0 (mean != 0.0), color it with this ROOT color value. Default: kYellow',
                      default='kYellow')
  parser.add_argument('--noMean',
                      type=str,
                      required=False,
                      dest='no_mean',
                      help='If a plot generated by a report has mean = 0.0, color it with this ROOT color value. Default: kOrange',
                      default='kOrange')

  # additional selections on properties and attributes
  parser.add_argument('--filterProps'  ,
                      type=str,
                      required=False,
                      dest='property_name_regex',
                      help='(INACTIVE) Regex specification for xAOD property names. Only used if --prop enabled.',
                      default='*')
  parser.add_argument('--filterAttrs',
                      type=str,
                      required=False,
                      dest='attribute_name_regex',
                      help='(INACTIVE) Regex specification for xAOD attribute names. Only used if --attr enabled.',
                      default='*')
  parser.add_argument('-i',
                      '--interactive',
                      dest='interactive',
                      action='store_true',
                      help='(INACTIVE) Flip on/off interactive mode allowing you to navigate through the container types and properties.')

  # parse the arguments, throw errors if missing any
  args = parser.parse_args()
  if args.property_name_regex != '*' or args.attribute_name_regex != '*' or args.interactive:
    parser.error("The following arguments have not been implemented yet: --filterProps, --filterAttrs, --interactive. Sorry for the inconvenience.")

  try:
    # start execution of actual program
    import timing

    # set verbosity for python printing
    if args.verbose < 5:
      dumpSG_logger.setLevel(25 - args.verbose*5)
    else:
      dumpSG_logger.setLevel(logging.NOTSET + 1)

    with tempfile.NamedTemporaryFile() as tmpFile:
      if not args.root_verbose:
        ROOT.gSystem.RedirectOutput(tmpFile.name, "w")

      # if flag is shown, set batch_mode to true, else false
      ROOT.gROOT.SetBatch(args.batch_mode)

      # load the xAOD EDM from RootCore and initialize
      #ROOT.gROOT.Macro('$ROOTCOREDIR/scripts/load_packages.C')
      #ROOT.xAOD.Init()

      # start by making a TChain
      dumpSG_logger.info("Initializing TChain")
      t = ROOT.TChain(args.tree_name)
      for fname in args.input_filename:
        if not os.path.isfile(fname):
          raise ValueError('The supplied input file `{0}` does not exist or I cannot find it.'.format(fname))
        else:
          dumpSG_logger.info("\tAdding {0}".format(fname))
          t.Add(fname)

      # Print some information
      dumpSG_logger.info('Number of input events: %s' % t.GetEntries())

      # first, just build up the whole dictionary
      xAOD_Objects = inspect_tree(t)

      # next, use the filters to cut down the dictionaries for outputting
      filtered_xAOD_Objects = filter_xAOD_objects(xAOD_Objects, args)

      # next, make a report -- add in information about mean, RMS, entries
      if args.make_report:
        make_report(t, filtered_xAOD_Objects, directory=args.output_directory, merge_report=args.merge_report)

      # dump to file
      dump_xAOD_objects(filtered_xAOD_Objects, args)

      dumpSG_logger.log(25, "All done!")

      if not args.root_verbose:
        ROOT.gROOT.ProcessLine("gSystem->RedirectOutput(0);")

  except Exception, e:
    # stop redirecting if we crash as well
    if not args.root_verbose:
      ROOT.gROOT.ProcessLine("gSystem->RedirectOutput(0);")

    dumpSG_logger.exception("{0}\nAn exception was caught!".format("-"*20))
