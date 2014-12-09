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

# First check if ROOTCOREDIR exists, implies ROOTCORE is set up
import os, sys
try:
  os.environ['ROOTCOREDIR']
except KeyError:
  print "It appears RootCore is not set up. Please set up RootCore and then try running me again."
  print "\tHint: try running `rcSetup`"
  sys.exit(1)

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


# Set up ROOT
import ROOT

def inspect_tree(t):
  xAOD_Objects = defaultdict(lambda: {'prop': [], 'attr': [], 'type': None, 'has_aux': False})  # list of properties and methods given Container Name

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
  xAOD_Container_Name = re.compile('^([^:]*)(?<!\.)$')
  xAOD_AuxContainer_Name = re.compile('(.*)Aux\.$')
  xAOD_Container_Prop = re.compile('(.*)Aux\.([^:]+)$')
  xAOD_Container_Attr = re.compile('(.*)AuxDyn\.([^:]+)$')
  xAOD_Type_Name = re.compile('^(vector<)?(.+?)(?(1)(?: ?>))$')
  xAOD_remove_version = re.compile('_v\d+')
  xAOD_Grab_Inner_Type = re.compile('<([^<>]*)>')

  # call them elements, because there are 4 types inside the leaves
  elements = t.GetListOfLeaves()
  for i in range(elements.GetEntries()):
    el = elements.At(i)

    # get the name of the element
    elName = el.GetName()
    # filter its type out
    elType = xAOD_remove_version.sub('', xAOD_Type_Name.search(el.GetTypeName()).groups()[1].replace('Aux','') )

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
    # set the property
    elif m_cont_prop:
      container, property = m_cont_prop.groups()
      xAOD_Objects[container]['prop'].append({'name': property, 'type': elType})
    # set the attribute
    elif m_cont_attr:
      container, attribute = m_cont_attr.groups()
      if 'btagging' in attribute.lower():
        attribute = attribute.replace('Link','')
        elType = xAOD_Grab_Inner_Type.search(elType).groups()[0] + ' *'
        xAOD_Objects[container]['prop'].append({'name': attribute, 'type': elType})
      else:
        xAOD_Objects[container]['attr'].append({'name': attribute, 'type': elType})
    elif m_cont_name:
      container, = m_cont_name.groups()
      xAOD_Objects[container]['type'] = xAOD_Objects[container]['type'] or elType  # initialize with defaults if not set already
 
  return xAOD_Objects

def filter_xAOD_objects(xAOD_Objects, args):
  p_container_name = re.compile(fnmatch.translate(args.container_name_regex))
  if args.has_aux:
    p_container_type = re.compile(fnmatch.translate('xAOD::%s' % args.container_type_regex))
  else:
    p_container_type = re.compile(fnmatch.translate(args.container_type_regex))

  # Python Level: EXPERT MODE
  filtered_xAOD_Objects = {k:{prop:val for prop, val in v.iteritems() if (args.list_properties and prop=='prop') or (args.list_attributes and prop=='attr') or prop in ['type','has_aux']} for (k,v) in xAOD_Objects.iteritems() if p_container_name.match(k) and p_container_type.match(v['type']) and (not args.has_aux or v['has_aux']) }
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

  parser = argparse.ArgumentParser(description='Process xAOD File and Dump Information.')
  # positional argument, require the first argument to be the input filename
  parser.add_argument('input_filename',
                      type=str,
                      help='an input root file to read')
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
                      default='xAOD_Info.dump')
  parser.add_argument('-t',
                      '--type',
                      type=str,
                      required=False,
                      dest='container_type_regex',
                      help='Regex specification for the xAOD container type. The `xAOD::` is automatically preprended. For example, --type="Jet*" will match `xAOD::JetContainer` while --type="*Jet*" will match `xAOD::TauJetContainer`. This uses Unix filename matching.',
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
  parser.add_argument('--has_aux',
                      dest='has_aux',
                      action='store_true',
                      help='Enable to only include containers which have an auxillary container. By default, it includes all containers it can find.')

  # additional verbosity arguments (flags)
  parser.add_argument('--prop',
                      dest='list_properties',
                      action='store_true',
                      help='Enable to print properties of container. By default, it only prints the xAOD::ContainerType and containers for that given type. This is like an increased verbosity option for container properties.')
  parser.add_argument('--attr',
                      dest='list_attributes',
                      action='store_true',
                      help='Enable to print attributes of container. By default, it only prints the xAOD::ContainerType and containers for that given type. This is like an increased verbosity option for container attributes.')

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
    print "The following arguments have not been implemented yet: --filterProps, --filterAttrs, --interactive. Sorry for the inconvenience. We will ignore these in the script."

  # load the xAOD EDM from RootCore and initialize
  ROOT.gROOT.Macro('$ROOTCOREDIR/scripts/load_packages.C')
  ROOT.xAOD.Init()

  # THIS IS FOR GIORDON TO TEST
  # fileName = '/share/t3data/kratsg/xAODs/mc14_13TeV.110351.PowhegPythia_P2012_ttbar_allhad.merge.AOD.e3232_s1982_s2008_r5787_r5853_tid01604209_00/AOD.01604209._000001.pool.root.1'
  
  if not os.path.isfile(args.input_filename):
    raise ValueError('The supplied input file `%s` does not exist or I cannot find it.' % args.input_filename)

  f = ROOT.TFile.Open(args.input_filename)
  # Make the "transient tree" ? I guess we don't need to
  # t = ROOT.xAOD.MakeTransientTree(f, args.tree_name)
  t = f.Get(args.tree_name)

  # Print some information
  print('Number of input events: %s' % t.GetEntries())

  # first, just build up the whole dictionary
  xAOD_Objects = inspect_tree(t)

  # next, use the filters to cut down the dictionaries
  filtered_xAOD_Objects = filter_xAOD_objects(xAOD_Objects, args)

  # dump to file
  dump_xAOD_objects(filtered_xAOD_Objects, args)
