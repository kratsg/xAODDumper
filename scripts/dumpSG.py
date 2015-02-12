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
dumpSG_logger = logging.getLogger('dumpSG')
dumpSG_logger.addHandler(logging.StreamHandler(STDOUT))

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
    if not args.verbose:
      ROOT.gSystem.RedirectOutput(tmpFile.name, "w")

    # execute code here  

    if not args.verbose:
      ROOT.gROOT.ProcessLine("gSystem->RedirectOutput(0);")
'''

# Set up ROOT
import ROOT

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

def save_plot(item, container, width=700, height=500, formats=['png'], directory="report"):
  with tempfile.NamedTemporaryFile() as tmpFile:
    if not args.verbose:
      ROOT.gSystem.RedirectOutput(tmpFile.name, "w")

    pathToImage = "{0}.png".format(os.path.join(directory, item['name']))
    c = ROOT.TCanvas(item['name'], item['name'], 200, 10, width, height)
    t.Draw(item['rootname'])
    c.SaveAs(pathToImage)

    # get histogram drawn and grab details
    htemp = c.GetPrimitive("htemp")

    if not args.verbose:
          ROOT.gROOT.ProcessLine("gSystem->RedirectOutput(0);")

  # if it didn't draw a histogram, there was an error drawing it
  if htemp == None:
    entries, mean, rms =  0, 0.0, 0.0
    drawable = False
  else:
    entries, mean, rms =  htemp.GetEntries(), htemp.GetMean(), htemp.GetRMS()
    drawable = True

  item['entries'] = entries
  item['mean'] = mean
  item['rms'] = rms
  item['drawable'] = drawable

  if drawable:
    # let the user know that this has RMS=0 and may be of interest
    if rms == 0:
      dumpSG_logger.warning("{0}/{1} might be problematic (RMS=0)\n\tpath:\t\t{2}\n\tmean:\t\t{3}\n\trms:\t\t{4}\n\tentries:\t{5}".format(container, item['name'], item['rootname'], item['mean'], item['rms'], item['entries']))
  else:
    errString = "{0}/{1} {{0}}\n\tpath:\t\t{2}".format(container, item['name'], item['rootname'])
    if 'ElementLink' in item['type']:
      # this is an example of what we can't draw normally
      dumpSG_logger.info(errString.format("is an ElementLink type"))
    elif t.GetLeaf(item['rootname']).GetValue(0) == 0:
      # this is when the values are missing, but Leaf.GetValue(0) returns 0.0
      #     not sure why, ask someone what the hell is going on
      dumpSG_logger.warning(errString.format("has missing values"))
    else:
      dumpSG_logger.warning(errString.format("couldn't be drawn"))

    # couldn't draw, remove it
    os.remove(pathToImage)

  del c

def make_report(t, xAOD_Objects, directory="report"):
  for container, items in xAOD_Objects.iteritems():
    sub_directory = os.path.join(directory,container)
    if not os.path.exists(sub_directory):
      os.makedirs(sub_directory)
    for prop in items.get('prop', []):
      save_plot(prop, container, directory=sub_directory)
    for prop in items.get('attr', []):
      save_plot(prop, container, directory=sub_directory)

  with open(os.path.join(directory, "info.json"), 'w+') as f:
    f.write(json.dumps(xAOD_Objects, sort_keys=True, indent=4))

  return True

def filter_xAOD_objects(xAOD_Objects, args):
  p_container_name = re.compile(fnmatch.translate(args.container_name_regex))
  p_container_type = re.compile(fnmatch.translate(args.container_type_regex))

  # Python Level: EXPERT MODE
  filtered_xAOD_Objects = {k:{prop:val for prop, val in v.iteritems() if (args.list_properties and prop=='prop') or (args.list_attributes and prop=='attr') or prop in ['type','has_aux','rootname']} for (k,v) in xAOD_Objects.iteritems() if p_container_name.match(k) and p_container_type.match(v['type']) and (not args.has_aux or v['has_aux']) }
  return filtered_xAOD_Objects

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
                      help='Specify the tree that contains the StoreGate structure.',
                      default='CollectionTree')
  parser.add_argument('-o',
                      '--output',
                      type=str,
                      required=False,
                      dest='output_filename',
                      help='Output file to store dumped information.',
                      default='info.dump')
  parser.add_argument('-d',
                      '--output_directory',
                      type=str,
                      required=False,
                      dest='output_directory',
                      help='Output directory to store the report generated.',
                      default='report')
  parser.add_argument('-t',
                      '--type',
                      type=str,
                      required=False,
                      dest='container_type_regex',
                      help='Regex specification for the xAOD container type. For example, --type="xAOD::Jet*" will match `xAOD::JetContainer` while --type="xAOD::*Jet*" will match `xAOD::TauJetContainer`. This uses Unix filename matching.',
                      default='*')
  parser.add_argument('-c',
                      '--container',
                      type=str,
                      required=False,
                      dest='container_name_regex',
                      help='Regex specification for the xAOD container name. For example, --container="AntiKt10LCTopo*" will match `AntiKt10LCTopoJets`. This uses Unix filename matching.',
                      default='*')
  parser.add_argument('-f',
                      '--format',
                      type=str,
                      required=False,
                      dest='output_format',
                      choices=['json','pickle','pretty'],
                      help='Specify the output format.',
                      default='pretty')
  parser.add_argument('-v',
                      '--verbose',
                      dest='verbose',
                      action='store_true',
                      help='Enable verbose output from ROOT\'s stdout.')
  parser.add_argument('-b',
                      '--batch',
                      dest='batch_mode',
                      action='store_true',
                      help='Enable batch mode for ROOT.')
  parser.add_argument('--has_aux',
                      dest='has_aux',
                      action='store_true',
                      help='Enable to only include containers which have an auxillary container. By default, it includes all containers it can find.')
  parser.add_argument('--prop',
                      dest='list_properties',
                      action='store_true',
                      help='Enable to print properties of container. By default, it only prints the xAOD::ContainerType and containers for that given type. This is like an increased verbosity option for container properties.')
  parser.add_argument('--attr',
                      dest='list_attributes',
                      action='store_true',
                      help='Enable to print attributes of container. By default, it only prints the xAOD::ContainerType and containers for that given type. This is like an increased verbosity option for container attributes.')
  parser.add_argument('--report',
                      dest='make_report',
                      action='store_true',
                      help='Enable to also create a directory containing plots and generate additional reporting information/statistics. By default, this is turned off as it can be potentially slow. The output directory containing the plots will be named `xAODDumper_Report`.')

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

  # start execution of actual program
  import timing

  # if flag is shown, set batch_mode to true, else false
  ROOT.gROOT.SetBatch(args.batch_mode)


  with tempfile.NamedTemporaryFile() as tmpFile:
    if not args.verbose:
      ROOT.gSystem.RedirectOutput(tmpFile.name, "w")

    # load the xAOD EDM from RootCore and initialize
    #ROOT.gROOT.Macro('$ROOTCOREDIR/scripts/load_packages.C')
    #ROOT.xAOD.Init()

    # start by making a TChain
    dumpSG_logger.info("Initializing TChain")
    t = ROOT.TChain(args.tree_name)
    for fname in args.input_filename:
      if not os.path.isfile(fname):
        dumpSG_logger.exception('The supplied input file `{0}` does not exist or I cannot find it.'.format(fname))
        raise ValueError
      else:
        dumpSG_logger.info("\tAdding {0}".format(fname))
        t.Add(fname)

    # f = ROOT.TFile.Open(args.input_filename)
    # Make the "transient tree" ? I guess we don't need to
    # t = ROOT.xAOD.MakeTransientTree(f, args.tree_name)
    # t = f.Get(args.tree_name)

    # Print some information
    # print('Number of input events: %s' % t.GetEntries())

    # first, just build up the whole dictionary
    xAOD_Objects = inspect_tree(t)

    # next, use the filters to cut down the dictionaries for outputting
    filtered_xAOD_Objects = filter_xAOD_objects(xAOD_Objects, args)

    # next, make a report -- add in information about mean, RMS, entries
    if args.make_report:
      make_report(t, filtered_xAOD_Objects, directory=args.output_directory)

    # dump to file
    dump_xAOD_objects(filtered_xAOD_Objects, args)

    dumpSG_logger.info("All done!")

    if not args.verbose:
      ROOT.gROOT.ProcessLine("gSystem->RedirectOutput(0);")
