
import json
import logging
import os
import random
import unittest
from copy import deepcopy as copy
from decimal import Decimal

from pynmrstar import utils, definitions, Saveframe, Entry, Schema, Loop, _Parser
from pynmrstar._internal import _interpret_file
from pynmrstar.exceptions import ParsingError

logging.getLogger('pynmrstar').setLevel(logging.ERROR)

our_path = os.path.dirname(os.path.realpath(__file__))
database_entry = Entry.from_database(15000)
sample_file_location = os.path.join(our_path, "sample_files", "bmr15000_3.str")
file_entry = Entry.from_file(sample_file_location)


class TestPyNMRSTAR(unittest.TestCase):

    def setUp(self):
        self.file_entry = copy(file_entry)
        self.maxDiff = None

    def test_clean_val(self):
        # Check tag cleaning
        self.assertEqual(utils.quote_value("single quote test"), "'single quote test'")
        self.assertEqual(utils.quote_value("double quote' test"), '"double quote\' test"')
        self.assertEqual(utils.quote_value("loop_"), "'loop_'")
        self.assertEqual(utils.quote_value("#comment"), "'#comment'")
        self.assertEqual(utils.quote_value("_tag"), "'_tag'")
        self.assertEqual(utils.quote_value("simple"), "simple")
        self.assertEqual(utils.quote_value("  "), "'  '")
        self.assertEqual(utils.quote_value("\nnewline\n"), "\nnewline\n")
        self.assertEqual(utils.quote_value(None), ".")
        self.assertRaises(ValueError, utils.quote_value, "")

        definitions.STR_CONVERSION_DICT = {"loop_": "noloop_"}
        utils.quote_value.cache_clear()
        self.assertEqual(utils.quote_value("loop_"), "noloop_")
        definitions.STR_CONVERSION_DICT = {None: "."}

    def test_odd_strings(self):
        """ Make sure the library can handle odd strings. """

        # Don't run the naughty strings test in GitHub, since it won't
        # recursively checkout the "naughty strings" module on platforms
        # other than linux.
        if "GITHUB_WORKFLOW" in os.environ:
            return

        saveframe = Saveframe.from_scratch('test', 'citations')
        with open(os.path.join(our_path, 'naughty-strings/blns.json')) as odd_string_file:
            odd_strings = json.load(odd_string_file)
        for x, string in enumerate(odd_strings):
            if string == '':
                continue
            saveframe.add_tag(str(x), string)

        self.assertEqual(saveframe, Saveframe.from_string(str(saveframe)))

    def test_edge_cases(self):
        """ Make sure that the various types of edge cases are properly handled. """

        Entry.from_file(os.path.join(our_path, 'sample_files', 'edge_cases.str'))
        Entry.from_file(os.path.join(our_path, 'sample_files', 'dos.str'))
        Entry.from_file(os.path.join(our_path, 'sample_files', 'nonewlines.str'))
        Entry.from_file(os.path.join(our_path, 'sample_files', 'onlynewlines.str'))

    def test__format_category(self):
        self.assertEqual(utils.format_category("test"), "_test")
        self.assertEqual(utils.format_category("_test"), "_test")
        self.assertEqual(utils.format_category("test.test"), "_test")

    def test__format_tag(self):
        self.assertEqual(utils.format_tag("test"), "test")
        self.assertEqual(utils.format_tag("_test.test"), "test")
        self.assertEqual(utils.format_tag("test.test"), "test")

    def test__InterpretFile(self):
        with open(sample_file_location, "r") as local_file:
            local_version = local_file.read()

        # Test reading file from local locations
        self.assertEqual(_interpret_file(sample_file_location).read(), local_version)
        with open(sample_file_location, "rb") as tmp:
            self.assertEqual(_interpret_file(tmp).read(), local_version)
        with open(os.path.join(our_path, "sample_files", "bmr15000_3.str.gz"), "rb") as tmp:
            self.assertEqual(_interpret_file(tmp).read(), local_version)

        # Test reading from http (ftp doesn't work on TravisCI)
        entry_url = 'https://bmrb.io/ftp/pub/bmrb/entry_directories/bmr15000/bmr15000_3.str'
        self.assertEqual(Entry.from_string(_interpret_file(entry_url).read()), database_entry)

        # Test reading from https locations
        raw_api_url = "https://api.bmrb.io/v2/entry/15000?format=rawnmrstar"
        self.assertEqual(Entry.from_string(_interpret_file(raw_api_url).read()), database_entry)

    # Test the parser
    def test___Parser(self):

        # Check for error when reserved token present in data value
        self.assertRaises(ParsingError, Entry.from_string, "data_1\nsave_1\n_tag.example loop_\nsave_\n")
        self.assertRaises(ParsingError, Entry.from_string, "data_1\nsave_1\n_tag.example data_\nsave_\n")
        self.assertRaises(ParsingError, Entry.from_string, "data_1\nsave_1\n_tag.example save_\nsave_\n")
        self.assertRaises(ParsingError, Entry.from_string, "data_1\nsave_1\nloop_\n_tag.tag\nloop_\nstop_\nsave_\n")
        self.assertRaises(ParsingError, Entry.from_string, "data_1\nsave_1\nloop_\n_tag.tag\nsave_\nstop_\nsave_\n")
        self.assertRaises(ParsingError, Entry.from_string, "data_1\nsave_1\nloop_\n_tag.tag\nglobal_\nstop_\nsave_\n")

        # Check for error when reserved token quoted
        self.assertRaises(ParsingError, Entry.from_string, "'data_1'\nsave_1\nloop_\n_tag.tag\ndata_\nstop_\nsave_\n")
        self.assertRaises(ParsingError, Entry.from_string, "data_1\n'save_1'\nloop_\n_tag.tag\ndata_\nstop_\nsave_\n")
        self.assertRaises(ParsingError, Entry.from_string, 'data_1\nsave_1\n"loop"_\n_tag.tag\ndata_\nstop_\nsave_\n')
        self.assertRaises(ParsingError, Entry.from_string,
                          "data_1\nsave_1\nloop_\n_tag.tag\ndata_\n;\nstop_\n;\nsave_\n")
        self.assertRaises(ParsingError, Saveframe.from_string, "save_1\n_tag.1 _tag.2")

    def test_Schema(self):
        default = Schema()

        self.assertEqual(default.headers,
                         ['Dictionary sequence', 'SFCategory', 'ADIT category mandatory', 'ADIT category view type',
                          'ADIT super category ID', 'ADIT super category', 'ADIT category group ID',
                          'ADIT category view name', 'Tag', 'BMRB current', 'Query prompt', 'Query interface',
                          'SG Mandatory', '', 'ADIT exists', 'User full view', 'Metabolomics', 'Metabolites', 'SENCI',
                          'Fragment library', 'Item enumerated', 'Item enumeration closed', 'Enum parent SFcategory',
                          'Enum parent tag', 'Derived enumeration mantable', 'Derived enumeration',
                          'ADIT item view name', 'Data Type', 'Nullable', 'Non-public', 'ManDBTableName',
                          'ManDBColumnName', 'Row Index Key', 'Saveframe ID tag', 'Source Key', 'Table Primary Key',
                          'Foreign Key Group', 'Foreign Table', 'Foreign Column', 'Secondary index', 'Sub category',
                          'Units', 'Loopflag', 'Seq', 'Adit initial rows', 'Enumeration ties',
                          'Mandatory code overides', 'Overide value', 'Overide view value', 'ADIT auto insert',
                          'Example', 'Prompt', 'Interface', 'bmrbPdbMatchID', 'bmrbPdbTransFunc', 'STAR flag',
                          'DB flag', 'SfNamelFlg', 'Sf category flag', 'Sf pointer', 'Natural primary key',
                          'Natural foreign key', 'Redundant keys', 'Parent tag', 'public', 'internal', 'small molecule',
                          'small molecule', 'metabolomics', 'Entry completeness', 'Overide public', 'internal',
                          'small molecule', 'small molecule', 'metabolomic', 'metabolomic', 'default value',
                          'Adit form code', 'Tag category', 'Tag field', 'Local key', 'Datum count flag',
                          'NEF equivalent', 'mmCIF equivalent', 'Meta data', 'Tag delete', 'BMRB data type',
                          'STAR vs Curated DB', 'Key group', 'Reference table', 'Reference column',
                          'Dictionary description', 'variableTypeMatch', 'entryIdFlg', 'outputMapExistsFlg',
                          'lclSfIdFlg', 'Met ADIT category view name', 'Met Example', 'Met Prompt', 'Met Description',
                          'SM Struct ADIT-NMR category view name', 'SM Struct Example', 'SM Struct Prompt',
                          'SM Struct Description', 'Met default value', 'SM default value'])

        self.assertEqual(default.val_type("_Entity.ID", 1), [])
        self.assertEqual(default.val_type("_Entity.ID", "test"), [
            "Value does not match specification: '_Entity.ID':'test'.\n     Type specified: int\n     "
            "Regular expression for type: '^(?:-?[0-9]*)?$'"])
        self.assertEqual(default.val_type("_Atom_chem_shift.Val", float(1.2)), [])
        self.assertEqual(default.val_type("_Atom_chem_shift.Val", "invalid"), [
            "Value does not match specification: '_Atom_chem_shift.Val':'invalid'.\n     Type "
            "specified: float\n     Regular expression for type: '^(?:-?[0-9]*\\.?[0-9]+(?:[eE][-+]?[0-9]+)?)?$'"])

        self.assertEqual(default.val_type("_Entry.ID", "this should be far too long - much too long"), [
            "Length of '43' is too long for 'CHAR(12)': '_Entry.ID':'this should be far too long - much too long'."])

    def test_entry_delitem(self):
        tmp_entry = copy(self.file_entry)
        tmp_entry.frame_list.pop(0)
        del self.file_entry[0]
        self.assertEqual(self.file_entry, tmp_entry)

    def test_duplicate_saveframe_errors(self):
        tmp_entry = copy(self.file_entry)
        self.assertRaises(ValueError, tmp_entry.add_saveframe, tmp_entry[0])
        tmp_entry.frame_list.append(tmp_entry[0])
        self.assertRaises(ValueError, tmp_entry.__getattribute__, 'frame_dict')

    def test_entry_eq(self):
        # Normalize them both first
        db_copy = copy(database_entry)
        db_copy.normalize()
        self.file_entry.normalize()
        self.assertEqual(self.file_entry, db_copy)

    def test_getitem(self):
        self.assertEqual(self.file_entry['entry_information'],
                         self.file_entry.get_saveframe_by_name("entry_information"))
        self.assertEqual(self.file_entry[0], self.file_entry.get_saveframe_by_name("entry_information"))

    def test_init(self):
        # Make sure the correct errors are raised
        self.assertRaises(ValueError, Entry)
        self.assertRaises(ParsingError, Entry, the_string="test", entry_num="test")
        # Make sure string parsing is correct
        self.assertEqual(self.file_entry, Entry.from_string(str(self.file_entry)))
        self.assertEqual(str(self.file_entry), str(Entry.from_string(str(self.file_entry))))
        self.assertRaises(IOError, Entry.from_database, 0)

        self.assertEqual(str(Entry.from_scratch(15000)), "data_15000\n\n")
        self.assertEqual(Entry.from_file(os.path.join(our_path, "sample_files", "bmr15000_3.str.gz")), self.file_entry)

    def test___setitem(self):
        tmp_entry = copy(self.file_entry)
        tmp_entry[0] = tmp_entry.get_saveframe_by_name('entry_information')
        self.assertEqual(tmp_entry, self.file_entry)
        tmp_entry['entry_information'] = tmp_entry.get_saveframe_by_name('entry_information')
        self.assertEqual(tmp_entry, self.file_entry)

        self.assertRaises(ValueError, tmp_entry.__setitem__, 'entry_informations',
                          tmp_entry.get_saveframe_by_name('entry_information'))
        self.assertRaises(ValueError, tmp_entry.__setitem__, 'entry_information', 1)

    def test_compare(self):
        self.assertEqual(self.file_entry.compare(str(self.file_entry)), [])
        self.assertEqual(self.file_entry.compare(self.file_entry), [])

        mutated = copy(self.file_entry)
        mutated.frame_list.pop()
        self.assertEqual(self.file_entry.compare(mutated),
                         ["The number of saveframes in the entries are not equal: '25' vs '24'.",
                          "No saveframe with name 'assigned_chem_shift_list_1' in other entry."])

    def test_getmethods(self):
        self.assertEqual(5, len(self.file_entry.get_loops_by_category("_Vendor")))
        self.assertEqual(5, len(self.file_entry.get_loops_by_category("vendor")))

        self.assertEqual(self.file_entry.get_saveframe_by_name('assigned_chem_shift_list_1'), self.file_entry[-1])
        self.assertRaises(KeyError, self.file_entry.get_saveframe_by_name, 'no such saveframe')

        self.assertEqual(len(self.file_entry.get_saveframes_by_category("NMR_spectrometer")), 6)
        self.assertEqual(len(self.file_entry.get_saveframes_by_category("nmr_SPectrometer")), 0)
        self.assertEqual(self.file_entry.get_saveframes_by_category('no such category'), [])

        self.assertEqual(self.file_entry.get_saveframes_by_tag_and_value('Submission_date', '2006-09-07'),
                         [self.file_entry[0]])
        self.assertEqual(self.file_entry.get_saveframes_by_tag_and_value('submission_Date', '2006-09-07'),
                         [self.file_entry[0]])
        self.assertEqual(self.file_entry.get_saveframes_by_tag_and_value('test.submission_date', '2006-09-07'), [])

        self.assertRaises(ValueError, self.file_entry.get_tag, 'bad_tag')
        self.assertEqual(self.file_entry.get_tag("entry.Submission_date"), ['2006-09-07'])
        self.assertEqual(self.file_entry.get_tag("entry.Submission_date", whole_tag=True),
                         [[u'Submission_date', u'2006-09-07']])

    def test_validate(self):
        validation = []
        self.assertEqual(self.file_entry.validate(), [])
        self.file_entry[-1][-1][0][0] = 'a'
        validation.append(
            "Value does not match specification: '_Atom_chem_shift.ID':'a'.\n     "
            "Type specified: int\n     Regular expression for type: '^(?:-?[0-9]*)?$'")
        self.assertEqual(self.file_entry.validate(), validation)
        self.file_entry[-1][-1][0][0] = '1'

    def test_saveframe(self):
        frame = self.file_entry[0]

        # Check __delitem__
        frame.remove_tag('DEtails')
        self.assertEqual([[x[0], x[1]] for x in frame.tags],
                         [['Sf_category', 'entry_information'],
                          ['Sf_framecode', 'entry_information'],
                          ['ID', '15000'],
                          ['Title',
                           'Solution structure of chicken villin headpiece subdomain containing a '
                           'fluorinated side chain in the core\n'],
                          ['Type', 'macromolecule'],
                          ['Version_type', 'original'],
                          ['Submission_date', '2006-09-07'],
                          ['Accession_date', '2006-09-07'],
                          ['Last_release_date', '2006-09-07'],
                          ['Original_release_date', '2006-09-07'],
                          ['Origination', 'author'],
                          ['Format_name', '.'],
                          ['NMR_STAR_version', '3.2.6.0'],
                          ['NMR_STAR_dict_location', '.'],
                          ['Original_NMR_STAR_version', '3.2.6.0'],
                          ['Experimental_method', 'NMR'],
                          ['Experimental_method_subtype', 'solution'],
                          ['Source_data_format', '.'],
                          ['Source_data_format_version', '.'],
                          ['Generated_software_name', '.'],
                          ['Generated_software_version', '.'],
                          ['Generated_software_ID', '.'],
                          ['Generated_software_label', '.'],
                          ['Generated_date', '.'],
                          ['DOI', '.'],
                          ['UUID', '.'],
                          ['Related_coordinate_file_name', '.'],
                          ['BMRB_internal_directory_name', '.']])
        self.assertEqual(len(frame), 7)
        del frame[0]
        self.assertEqual(len(frame), 6)
        del frame[frame.get_loop('RElease')]
        self.assertEqual(len(frame), 5)
        self.assertRaises(KeyError, frame.get_loop, 'RElease')

        # Check __getitem__
        self.assertEqual(frame.get_tag('NMR_STAR_version'), ['3.2.6.0'])
        self.assertEqual(frame[0], frame.loops[0])
        self.assertEqual(frame.get_loop('_SG_project'), frame.loops[0])

        # Check __lt__
        self.assertEqual(frame[-3] > frame[-1], False)

        # Check __init__
        self.assertRaises(ValueError, Saveframe)
        self.assertEqual(Saveframe.from_string(str(frame)), frame)
        self.assertEqual(str(Saveframe.from_scratch("test", tag_prefix="test")), "save_test\n\nsave_\n")
        tmp = copy(frame)
        tmp._loops = []
        self.assertEqual(Saveframe.from_string(frame.get_data_as_csv(frame), csv=True).compare(tmp), [])
        self.assertRaises(ValueError, Saveframe.from_string, "test.1,test.2\n2,3,4", csv=True)

        # Check __repr__
        self.assertEqual(repr(frame), "<pynmrstar.Saveframe 'entry_information'>")

        # Check __setitem__
        frame['test'] = 1
        self.assertEqual(frame.tags[-1][1], 1)
        frame['tESt'] = 2
        self.assertEqual(frame.tags[-1][1], 2)
        frame[4] = frame[3]
        self.assertEqual(frame.loops[3], frame.loops[4])

        # Check add_loop
        self.assertRaises(ValueError, frame.add_loop, frame.loops[0])

        # Check add_tag
        self.assertRaises(ValueError, frame.add_tag, "test", 1)
        self.assertRaises(ValueError, frame.add_tag, "invalid test", 1)
        self.assertRaises(ValueError, frame.add_tag, "invalid.test.test", 1)
        self.assertRaises(ValueError, frame.add_tag, "invalid.test", 1, update=True)
        frame.add_tag("test", 3, update=True)
        self.assertEqual(frame.get_tag('test'), [3])

        # Check add_tags
        frame.add_tags([['example1'], ['example2']])
        self.assertEqual(frame.tags[-2], ['example1', "."])
        frame.add_tags([['example1', 5], ['example2']], update=True)
        self.assertEqual(frame.tags[-2], ['example1', 5])

        # Check compare
        self.assertEqual(frame.compare(frame), [])
        self.assertEqual(frame.compare(self.file_entry[1]),
                         ["\tSaveframe names do not match: 'entry_information' vs 'citation_1'."])
        tmp = copy(frame)
        tmp.tag_prefix = "test"
        self.assertEqual(frame.compare(tmp), ["\tTag prefix does not match: '_Entry' vs 'test'."])
        tmp = copy(frame)
        tmp.tags[0][0] = "broken"
        self.assertEqual(frame.compare(tmp), ["\tNo tag with name '_Entry.Sf_category' in compared entry."])

        # Test remove_tag
        self.assertRaises(KeyError, frame.remove_tag, "this_tag_will_not_exist")
        frame.remove_tag("test")
        self.assertEqual(frame.get_tag("test"), [])

        # Test get_data_as_csv
        self.assertEqual(frame.get_data_as_csv(),
                         '''_Entry.Sf_category,_Entry.Sf_framecode,_Entry.ID,_Entry.Title,_Entry.Type,_Entry.Version_type,_Entry.Submission_date,_Entry.Accession_date,_Entry.Last_release_date,_Entry.Original_release_date,_Entry.Origination,_Entry.Format_name,_Entry.NMR_STAR_version,_Entry.NMR_STAR_dict_location,_Entry.Original_NMR_STAR_version,_Entry.Experimental_method,_Entry.Experimental_method_subtype,_Entry.Source_data_format,_Entry.Source_data_format_version,_Entry.Generated_software_name,_Entry.Generated_software_version,_Entry.Generated_software_ID,_Entry.Generated_software_label,_Entry.Generated_date,_Entry.DOI,_Entry.UUID,_Entry.Related_coordinate_file_name,_Entry.BMRB_internal_directory_name,_Entry.example1,_Entry.example2
entry_information,entry_information,15000,"Solution structure of chicken villin headpiece subdomain containing a fluorinated side chain in the core
",macromolecule,original,2006-09-07,2006-09-07,2006-09-07,2006-09-07,author,.,3.2.6.0,.,3.2.6.0,NMR,solution,.,.,.,.,.,.,.,.,.,.,.,5,.
''')
        self.assertEqual(frame.get_data_as_csv(show_category=False),
                         '''Sf_category,Sf_framecode,ID,Title,Type,Version_type,Submission_date,Accession_date,Last_release_date,Original_release_date,Origination,Format_name,NMR_STAR_version,NMR_STAR_dict_location,Original_NMR_STAR_version,Experimental_method,Experimental_method_subtype,Source_data_format,Source_data_format_version,Generated_software_name,Generated_software_version,Generated_software_ID,Generated_software_label,Generated_date,DOI,UUID,Related_coordinate_file_name,BMRB_internal_directory_name,example1,example2
entry_information,entry_information,15000,"Solution structure of chicken villin headpiece subdomain containing a fluorinated side chain in the core
",macromolecule,original,2006-09-07,2006-09-07,2006-09-07,2006-09-07,author,.,3.2.6.0,.,3.2.6.0,NMR,solution,.,.,.,.,.,.,.,.,.,.,.,5,.
''')
        self.assertEqual(frame.get_data_as_csv(header=False),
                         '''entry_information,entry_information,15000,"Solution structure of chicken villin headpiece subdomain containing a fluorinated side chain in the core
",macromolecule,original,2006-09-07,2006-09-07,2006-09-07,2006-09-07,author,.,3.2.6.0,.,3.2.6.0,NMR,solution,.,.,.,.,.,.,.,.,.,.,.,5,.
''')
        self.assertEqual(frame.get_data_as_csv(show_category=False, header=False),
                         '''entry_information,entry_information,15000,"Solution structure of chicken villin headpiece subdomain containing a fluorinated side chain in the core
",macromolecule,original,2006-09-07,2006-09-07,2006-09-07,2006-09-07,author,.,3.2.6.0,.,3.2.6.0,NMR,solution,.,.,.,.,.,.,.,.,.,.,.,5,.
''')

        # Test get_loop
        self.assertEqual(repr(frame.get_loop("_SG_projecT")), "<pynmrstar.Loop '_SG_project'>")
        self.assertRaises(KeyError, frame.get_loop, 'this_loop_wont_be_found')

        # Test get_tag - this is really already tested in the other tests here
        self.assertEqual(frame.get_tag("sf_category"), ['entry_information'])
        self.assertEqual(frame.get_tag("entry.sf_category"), ['entry_information'])
        self.assertEqual(frame.get_tag("entry.sf_category", whole_tag=True), [['Sf_category', 'entry_information']])

        # Test sort
        self.assertEqual([[x[0], x[1]] for x in frame.tags], [['Sf_category', 'entry_information'],
                                                              ['Sf_framecode', 'entry_information'],
                                                              ['ID', '15000'],
                                                              ['Title',
                                                               'Solution structure of chicken villin headpiece subdomain containing a '
                                                               'fluorinated side chain in the core\n'],
                                                              ['Type', 'macromolecule'],
                                                              ['Version_type', 'original'],
                                                              ['Submission_date', '2006-09-07'],
                                                              ['Accession_date', '2006-09-07'],
                                                              ['Last_release_date', '2006-09-07'],
                                                              ['Original_release_date', '2006-09-07'],
                                                              ['Origination', 'author'],
                                                              ['Format_name', '.'],
                                                              ['NMR_STAR_version', '3.2.6.0'],
                                                              ['NMR_STAR_dict_location', '.'],
                                                              ['Original_NMR_STAR_version', '3.2.6.0'],
                                                              ['Experimental_method', 'NMR'],
                                                              ['Experimental_method_subtype', 'solution'],
                                                              ['Source_data_format', '.'],
                                                              ['Source_data_format_version', '.'],
                                                              ['Generated_software_name', '.'],
                                                              ['Generated_software_version', '.'],
                                                              ['Generated_software_ID', '.'],
                                                              ['Generated_software_label', '.'],
                                                              ['Generated_date', '.'],
                                                              ['DOI', '.'],
                                                              ['UUID', '.'],
                                                              ['Related_coordinate_file_name', '.'],
                                                              ['BMRB_internal_directory_name', '.'],
                                                              ['example1', 5],
                                                              ['example2', '.']])

        frame.remove_tag(['example2', 'example1'])
        frame.tags.append(frame.tags.pop(0))
        frame.sort_tags()
        self.assertEqual([[x[0], x[1]] for x in frame.tags], [['Sf_category', 'entry_information'],
                                                              ['Sf_framecode', 'entry_information'],
                                                              ['ID', '15000'],
                                                              ['Title',
                                                               'Solution structure of chicken villin headpiece subdomain containing a '
                                                               'fluorinated side chain in the core\n'],
                                                              ['Type', 'macromolecule'],
                                                              ['Version_type', 'original'],
                                                              ['Submission_date', '2006-09-07'],
                                                              ['Accession_date', '2006-09-07'],
                                                              ['Last_release_date', '2006-09-07'],
                                                              ['Original_release_date', '2006-09-07'],
                                                              ['Origination', 'author'],
                                                              ['Format_name', '.'],
                                                              ['NMR_STAR_version', '3.2.6.0'],
                                                              ['NMR_STAR_dict_location', '.'],
                                                              ['Original_NMR_STAR_version', '3.2.6.0'],
                                                              ['Experimental_method', 'NMR'],
                                                              ['Experimental_method_subtype', 'solution'],
                                                              ['Source_data_format', '.'],
                                                              ['Source_data_format_version', '.'],
                                                              ['Generated_software_name', '.'],
                                                              ['Generated_software_version', '.'],
                                                              ['Generated_software_ID', '.'],
                                                              ['Generated_software_label', '.'],
                                                              ['Generated_date', '.'],
                                                              ['DOI', '.'],
                                                              ['UUID', '.'],
                                                              ['Related_coordinate_file_name', '.'],
                                                              ['BMRB_internal_directory_name', '.']])

        # Test validate
        self.assertEqual(self.file_entry['assigned_chem_shift_list_1'].validate(), [])

        # Test set_tag_prefix
        frame.set_tag_prefix("new_prefix")
        self.assertEqual(frame.tag_prefix, "_new_prefix")

    def test_Saveframe_add_tag(self):
        """ Test the add_tag functionality of a saveframe. """

        # Test that you cannot set the framecode to a null value
        test_sf = Saveframe.from_scratch('test')

        # Test that the initial setter can't set a null value
        with self.assertRaises(ValueError):
            test_sf.add_tag('sf_framecode', None)
        test_sf.add_tag('sf_framecode', 'test')

        # Test that updating both via add_tag(update=True) and .name= don't
        # allow for setting a null value
        for val in definitions.NULL_VALUES:
            with self.assertRaises(ValueError):
                test_sf.add_tag('sf_framecode', val)
            with self.assertRaises(ValueError):
                test_sf.name = val

        # Test that adding an sf_framecode with a different value than the
        #  saveframe name throws an exception
        with self.assertRaises(ValueError):
            test_sf_two = Saveframe.from_scratch('test')
            test_sf_two.add_tag('sf_framecode', 'different')

    def test_Entry___setitem__(self):
        """ Test the setting a tag functionality of an entry. """

        test_entry = Entry.from_scratch('test')
        test_saveframe = Saveframe.from_scratch('test', 'test')
        test_entry._frame_list = [test_saveframe, test_saveframe]
        with self.assertRaises(ValueError):
            test_entry['test'] = test_saveframe

    def test_category_list(self):
        """ Test the category list property. """

        tmp = copy(self.file_entry)
        self.assertEqual(tmp.category_list, ['entry_information', 'citations', 'assembly', 'entity', 'natural_source',
                                             'experimental_source', 'chem_comp', 'sample', 'sample_conditions',
                                             'software', 'NMR_spectrometer', 'NMR_spectrometer_list', 'experiment_list',
                                             'chem_shift_reference', 'assigned_chemical_shifts'])
        tmp.add_saveframe(Saveframe.from_scratch("test", None))
        self.assertEqual(tmp.category_list, ['entry_information', 'citations', 'assembly', 'entity', 'natural_source',
                                             'experimental_source', 'chem_comp', 'sample', 'sample_conditions',
                                             'software', 'NMR_spectrometer', 'NMR_spectrometer_list', 'experiment_list',
                                             'chem_shift_reference', 'assigned_chemical_shifts'])

    def test_loop_parsing(self):
        with self.assertRaises(ParsingError):
            Loop.from_string("loop_ _test.one _test.two 1 loop_")
        with self.assertRaises(ParsingError):
            Loop.from_string("loop_ _test.one _test.two 1 stop_")
        with self.assertRaises(ParsingError):
            Loop.from_string("loop_ _test.one _test.two 1 2 3 stop_")
        with self.assertRaises(ParsingError):
            Loop.from_string("loop_ _test.one _test.two 1 2 3")
        with self.assertRaises(ParsingError):
            Loop.from_string("loop_ _test.one _test.two 1 save_ stop_")

    def test_loop(self):
        test_loop = self.file_entry[0][0]

        # Check filter
        self.assertEqual(test_loop.filter(['_Entry_author.Ordinal', '_Entry_author.Middle_initials']),
                         Loop.from_string(
                             "loop_ _Entry_author.Ordinal _Entry_author.Middle_initials 1 C. 2 . 3 B. 4 H. 5 L. stop_"))
        # Check eq
        self.assertEqual(test_loop == self.file_entry[0][0], True)
        self.assertEqual(test_loop != self.file_entry[0][1], True)
        # Check __getitem__
        self.assertEqual(test_loop['_Entry_author.Ordinal'], ['1', '2', '3', '4', '5'])
        self.assertEqual(test_loop[['_Entry_author.Ordinal', '_Entry_author.Middle_initials']],
                         [['1', 'C.'], ['2', '.'], ['3', 'B.'], ['4', 'H.'], ['5', 'L.']])
        # Test __setitem__
        test_loop['_Entry_author.Ordinal'] = [1] * 5
        self.assertEqual(test_loop['_Entry_author.Ordinal'], [1, 1, 1, 1, 1])
        test_loop['_Entry_author.Ordinal'] = ['1', '2', '3', '4', '5']
        self.assertRaises(ValueError, test_loop.__setitem__, '_Entry_author.Ordinal', [1])
        self.assertRaises(ValueError, test_loop.__setitem__, '_Wrong_loop.Ordinal', [1, 2, 3, 4, 5])
        # Check __init__
        self.assertRaises(ValueError, Loop)
        test = Loop.from_scratch(category="test")
        self.assertEqual(test.category, "_test")
        self.assertEqual(Loop.from_string(str(test_loop)), test_loop)
        self.assertEqual(test_loop, Loop.from_string(test_loop.get_data_as_csv(), csv=True))
        # Check len
        self.assertEqual(len(test_loop), len(test_loop.data))
        # Check lt
        self.assertEqual(test_loop < self.file_entry[0][1], True)
        # Check __str__
        self.assertEqual(Loop.from_scratch().format(skip_empty_loops=False), "\n   loop_\n\n   stop_\n")
        self.assertEqual(Loop.from_scratch().format(skip_empty_loops=True), "")
        tmp_loop = Loop.from_scratch()
        tmp_loop.data = [[1, 2, 3]]
        self.assertRaises(ValueError, tmp_loop.__str__)
        tmp_loop.add_tag("tag1")
        self.assertRaises(ValueError, tmp_loop.__str__)
        tmp_loop.add_tag("tag2")
        tmp_loop.add_tag("tag3")
        self.assertRaises(ValueError, tmp_loop.__str__)
        tmp_loop.set_category("test")
        self.assertEqual(str(tmp_loop), "\n   loop_\n      _test.tag1\n      _test.tag2\n      _test.tag3\n\n     "
                                        "1   2   3    \n\n   stop_\n")
        self.assertEqual(tmp_loop.category, "_test")
        # Check different category
        self.assertRaises(ValueError, tmp_loop.add_tag, "invalid.tag")
        # Check duplicate tag
        self.assertRaises(ValueError, tmp_loop.add_tag, "test.tag3")
        self.assertEqual(tmp_loop.add_tag("test.tag3", ignore_duplicates=True), None)
        # Check space and period in tag
        self.assertRaises(ValueError, tmp_loop.add_tag, "test. tag")
        self.assertRaises(ValueError, tmp_loop.add_tag, "test.tag.test")

        # Check add_data
        self.assertRaises(ValueError, tmp_loop.add_data, [1, 2, 3, 4])
        tmp_loop.add_data([4, 5, 6])
        tmp_loop.add_data([7, 8, 9])
        self.assertEqual(tmp_loop.data, [[1, 2, 3], [4, 5, 6], [7, 8, 9]])

        # Test delete_data_by_tag_value
        self.assertEqual(tmp_loop.remove_data_by_tag_value("tag1", 1, index_tag=0), [[1, 2, 3]])
        self.assertRaises(ValueError, tmp_loop.remove_data_by_tag_value, "tag4", "data")
        self.assertEqual(tmp_loop.data, [[1, 5, 6], [2, 8, 9]])

        # Test get_data_as_csv()
        self.assertEqual(tmp_loop.get_data_as_csv(), "_test.tag1,_test.tag2,_test.tag3\n1,5,6\n2,8,9\n")
        self.assertEqual(tmp_loop.get_data_as_csv(show_category=False), "tag1,tag2,tag3\n1,5,6\n2,8,9\n")
        self.assertEqual(tmp_loop.get_data_as_csv(header=False), "1,5,6\n2,8,9\n")
        self.assertEqual(tmp_loop.get_data_as_csv(show_category=False, header=False), "1,5,6\n2,8,9\n")

        # Test get_tag
        self.assertRaises(ValueError, tmp_loop.get_tag, "invalid.tag1")
        self.assertEqual(tmp_loop.get_tag("tag1"), [1, 2])
        self.assertEqual(tmp_loop.get_tag(["tag1", "tag2"]), [[1, 5], [2, 8]])
        self.assertEqual(tmp_loop.get_tag("tag1", whole_tag=True), [['_test.tag1', 1], ['_test.tag1', 2]])

        self.assertEqual(
            test_loop.get_tag(['_Entry_author.Ordinal', '_Entry_author.Middle_initials'], dict_result=True),
            [{'Middle_initials': 'C.', 'Ordinal': '1'}, {'Middle_initials': '.', 'Ordinal': '2'},
             {'Middle_initials': 'B.', 'Ordinal': '3'}, {'Middle_initials': 'H.', 'Ordinal': '4'},
             {'Middle_initials': 'L.', 'Ordinal': '5'}])

        self.assertEqual(test_loop.get_tag(['_Entry_author.Ordinal', '_Entry_author.Middle_initials'], dict_result=True,
                                           whole_tag=True),
                         [{'_Entry_author.Middle_initials': 'C.', '_Entry_author.Ordinal': '1'},
                          {'_Entry_author.Middle_initials': '.', '_Entry_author.Ordinal': '2'},
                          {'_Entry_author.Middle_initials': 'B.', '_Entry_author.Ordinal': '3'},
                          {'_Entry_author.Middle_initials': 'H.', '_Entry_author.Ordinal': '4'},
                          {'_Entry_author.Middle_initials': 'L.', '_Entry_author.Ordinal': '5'}])

        def simple_key(x):
            return -int(x[2])

        # Test sort_rows
        tmp_loop.sort_rows(["tag2"], key=simple_key)
        self.assertEqual(tmp_loop.data, [[2, 8, 9], [1, 5, 6]])
        tmp_loop.sort_rows(["tag2"])
        self.assertEqual(tmp_loop.data, [[1, 5, 6], [2, 8, 9]])

        # Test clear data
        tmp_loop.clear_data()
        self.assertEqual(tmp_loop.data, [])

        # Test that the from_template method works
        self.assertEqual(Loop.from_template("atom_chem_shift", all_tags=False),
                         Loop.from_string("""
loop_
      _Atom_chem_shift.ID
      _Atom_chem_shift.Assembly_atom_ID
      _Atom_chem_shift.Entity_assembly_ID
      _Atom_chem_shift.Entity_assembly_asym_ID
      _Atom_chem_shift.Entity_ID
      _Atom_chem_shift.Comp_index_ID
      _Atom_chem_shift.Seq_ID
      _Atom_chem_shift.Comp_ID
      _Atom_chem_shift.Atom_ID
      _Atom_chem_shift.Atom_type
      _Atom_chem_shift.Atom_isotope_number
      _Atom_chem_shift.Val
      _Atom_chem_shift.Val_err
      _Atom_chem_shift.Assign_fig_of_merit
      _Atom_chem_shift.Ambiguity_code
      _Atom_chem_shift.Ambiguity_set_ID
      _Atom_chem_shift.Occupancy
      _Atom_chem_shift.Resonance_ID
      _Atom_chem_shift.Auth_entity_assembly_ID
      _Atom_chem_shift.Auth_asym_ID
      _Atom_chem_shift.Auth_seq_ID
      _Atom_chem_shift.Auth_comp_ID
      _Atom_chem_shift.Auth_atom_ID
      _Atom_chem_shift.Original_PDB_strand_ID
      _Atom_chem_shift.Original_PDB_residue_no
      _Atom_chem_shift.Original_PDB_residue_name
      _Atom_chem_shift.Original_PDB_atom_name
      _Atom_chem_shift.Details
      _Atom_chem_shift.Entry_ID
      _Atom_chem_shift.Assigned_chem_shift_list_ID


   stop_
"""))

        self.assertEqual(Loop.from_template("atom_chem_shift", all_tags=True),
                         Loop.from_string("""
   loop_
      _Atom_chem_shift.ID
      _Atom_chem_shift.Assembly_atom_ID
      _Atom_chem_shift.Entity_assembly_ID
      _Atom_chem_shift.Entity_assembly_asym_ID
      _Atom_chem_shift.Entity_ID
      _Atom_chem_shift.Comp_index_ID
      _Atom_chem_shift.Seq_ID
      _Atom_chem_shift.Comp_ID
      _Atom_chem_shift.Atom_ID
      _Atom_chem_shift.Atom_type
      _Atom_chem_shift.Atom_isotope_number
      _Atom_chem_shift.Val
      _Atom_chem_shift.Val_err
      _Atom_chem_shift.Assign_fig_of_merit
      _Atom_chem_shift.Ambiguity_code
      _Atom_chem_shift.Ambiguity_set_ID
      _Atom_chem_shift.Occupancy
      _Atom_chem_shift.Resonance_ID
      _Atom_chem_shift.Auth_entity_assembly_ID
      _Atom_chem_shift.Auth_asym_ID
      _Atom_chem_shift.Auth_seq_ID
      _Atom_chem_shift.Auth_comp_ID
      _Atom_chem_shift.Auth_atom_ID
      _Atom_chem_shift.PDB_record_ID
      _Atom_chem_shift.PDB_model_num
      _Atom_chem_shift.PDB_strand_ID
      _Atom_chem_shift.PDB_ins_code
      _Atom_chem_shift.PDB_residue_no
      _Atom_chem_shift.PDB_residue_name
      _Atom_chem_shift.PDB_atom_name
      _Atom_chem_shift.Original_PDB_strand_ID
      _Atom_chem_shift.Original_PDB_residue_no
      _Atom_chem_shift.Original_PDB_residue_name
      _Atom_chem_shift.Original_PDB_atom_name
      _Atom_chem_shift.Details
      _Atom_chem_shift.Sf_ID
      _Atom_chem_shift.Entry_ID
      _Atom_chem_shift.Assigned_chem_shift_list_ID


   stop_
"""))

        # Test adding a tag to the schema
        my_schem = Schema()
        my_schem.add_tag("_Atom_chem_shift.New_Tag", "VARCHAR(100)", True, "assigned_chemical_shifts", True,
                         "_Atom_chem_shift.Atom_ID")
        self.assertEqual(Loop.from_template("atom_chem_shift", all_tags=True, schema=my_schem),
                         Loop.from_string(
                             "loop_ _Atom_chem_shift.ID _Atom_chem_shift.Assembly_atom_ID "
                             "_Atom_chem_shift.Entity_assembly_ID _Atom_chem_shift.Entity_ID "
                             "_Atom_chem_shift.Comp_index_ID _Atom_chem_shift.Seq_ID "
                             "_Atom_chem_shift.Comp_ID _Atom_chem_shift.Atom_ID _Atom_chem_shift.New_Tag "
                             "_Atom_chem_shift.Atom_type _Atom_chem_shift.Atom_isotope_number "
                             "_Atom_chem_shift.Val _Atom_chem_shift.Val_err _Atom_chem_shift.Assign_fig_of_merit "
                             "_Atom_chem_shift.Ambiguity_code _Atom_chem_shift.Ambiguity_set_ID "
                             "_Atom_chem_shift.Occupancy _Atom_chem_shift.Resonance_ID "
                             "_Atom_chem_shift.Auth_entity_assembly_ID _Atom_chem_shift.Auth_asym_ID "
                             "_Atom_chem_shift.Auth_seq_ID _Atom_chem_shift.Auth_comp_ID "
                             "_Atom_chem_shift.Auth_atom_ID _Atom_chem_shift.PDB_record_ID "
                             "_Atom_chem_shift.PDB_model_num _Atom_chem_shift.PDB_strand_ID "
                             "_Atom_chem_shift.PDB_ins_code _Atom_chem_shift.PDB_residue_no "
                             "_Atom_chem_shift.PDB_residue_name _Atom_chem_shift.PDB_atom_name "
                             "_Atom_chem_shift.Original_PDB_strand_ID _Atom_chem_shift.Original_PDB_residue_no "
                             "_Atom_chem_shift.Original_PDB_residue_name _Atom_chem_shift.Original_PDB_atom_name "
                             "_Atom_chem_shift.Details _Atom_chem_shift.Sf_ID _Atom_chem_shift.Entry_ID "
                             "_Atom_chem_shift.Assigned_chem_shift_list_ID stop_ "))

        # Make sure adding data with a tag works
        tmp_loop = Loop.from_string("loop_ _Atom_chem_shift.ID stop_")
        tmp_loop.data = [[1]]
        tmp_loop.add_tag("Assembly_atom_ID", update_data=True)
        self.assertEqual(tmp_loop.data, [[1, None]])
        self.assertEqual(tmp_loop.tags, ["ID", "Assembly_atom_ID"])

        # Make sure the add missing tags loop is working
        tmp_loop = Loop.from_string("loop_ _Atom_chem_shift.ID stop_")
        tmp_loop.add_missing_tags()
        self.assertEqual(tmp_loop, Loop.from_template("atom_chem_shift"))

    def test_loop_add_data(self):
        test1 = Loop.from_scratch('test')
        test1.add_tag(['Name', 'Location'])
        self.assertRaises(ValueError, test1.add_data, None)
        self.assertRaises(ValueError, test1.add_data, [])
        self.assertRaises(ValueError, test1.add_data, {})
        self.assertRaises(ValueError, test1.add_data, {'not_present': 1})
        test1.add_data([{'name': 'Jeff', 'location': 'Connecticut'}, {'name': 'Chad', 'location': 'Madison'}])

        test2 = Loop.from_scratch('test')
        test2.add_tag(['Name', 'Location'])
        test2.add_data({'name': ['Jeff', 'Chad'], 'location': ['Connecticut', 'Madison']})

        test3 = Loop.from_scratch('test')
        test3.add_tag(['Name', 'Location'])
        self.assertRaises(ValueError, test3.add_data, [['Jeff', 'Connecticut'], ['Chad']])
        test3.add_data([['Jeff', 'Connecticut'], ['Chad', 'Madison']])

        test4 = Loop.from_scratch('test')
        test4.add_tag(['Name', 'Location'])
        self.assertRaises(ValueError, test4.add_data, ['Jeff', 'Connecticut', 'Chad', 'Madison'])
        test4.add_data(['Jeff', 'Connecticut', 'Chad', 'Madison'], rearrange=True)

        self.assertEqual(test1, test2)
        self.assertEqual(test2, test3)
        self.assertEqual(test3, test4)

        # Now check the 'convert_data_types' argument and the raw data present in the loop
        test = Loop.from_scratch('_Atom_chem_shift')
        test.add_tag(['Val', 'Entry_ID', 'Details'])
        test.add_data([{'details': 'none', 'vAL': '1.2'}, {'val': 5, 'details': '.'}], convert_data_types=True)
        self.assertEqual(test.data, [[Decimal('1.2'), None, 'none'], [Decimal(5), None, None]])
        test.clear_data()
        test.add_data([{'details': 'none', 'vAL': '1.2'}, {'val': 5, 'details': '.'}])
        self.assertEqual(test.data, [['1.2', None, 'none'], [5, None, '.']])

    def test_rename_saveframe(self):
        tmp = copy(self.file_entry)
        tmp.rename_saveframe('F5-Phe-cVHP', 'jons_frame')
        tmp.rename_saveframe('jons_frame', 'F5-Phe-cVHP')
        self.assertEqual(tmp, self.file_entry)

    def test_duplicate_loop_detection(self):
        one = Loop.from_scratch(category="duplicate")
        two = Loop.from_scratch(category="duplicate")
        frame = Saveframe.from_scratch('1')
        frame.add_loop(one)
        self.assertRaises(ValueError, frame.add_loop, two)

    def test_normalize(self):

        db_tmp = copy(self.file_entry)
        denormalized = Entry.from_file(os.path.join(our_path, "sample_files", "bmr15000_3_denormalized.str"))
        denormalized.normalize()
        self.assertEqual(db_tmp.compare(denormalized), [])

        # Shuffle our local entry
        random.shuffle(db_tmp.frame_list)
        for frame in db_tmp:
            random.shuffle(frame.loops)
            random.shuffle(frame.tags)

        # Might as well test equality testing while shuffled:
        self.assertEqual(db_tmp.compare(self.file_entry), [])

        # Test that the frames are in a different order
        self.assertNotEqual(db_tmp.frame_list, self.file_entry.frame_list)
        db_tmp.normalize()

        self.assertEqual(db_tmp.frame_list, self.file_entry.frame_list)

        # Now test ordering of saveframes when tags may be missing
        b = Saveframe.from_scratch('not_real2')
        b.add_tag('_help.Sf_category', 'a')
        b.add_tag('_help.ID', 1)
        c = Saveframe.from_scratch('not_real')
        c.add_tag('_help.Sf_category', 'a')
        c.add_tag('_help.ID', 'a')
        d = Saveframe.from_scratch('not_real3')
        d.add_tag('_help.borg', 'a')

        db_tmp.add_saveframe(b)
        db_tmp.add_saveframe(c)
        db_tmp.add_saveframe(d)

        correct_order = db_tmp.frame_list[:]
        random.shuffle(db_tmp.frame_list)
        db_tmp.normalize()
        self.assertEqual(db_tmp.frame_list, correct_order)

    def test_syntax_outliers(self):
        """ Make sure the case of semi-colon delineated data in a data
        value is properly escaped. """

        ml = copy(self.file_entry[0][0])
        # Should always work once
        ml[0][0] = str(ml)
        self.assertEqual(ml, Loop.from_string(str(ml)))
        # Twice could trigger bug
        ml[0][0] = str(ml)
        self.assertEqual(ml, Loop.from_string(str(ml)))
        self.assertEqual(ml[0][0], Loop.from_string(str(ml))[0][0])
        # Third time is a charm
        ml[0][0] = str(ml)
        self.assertEqual(ml, Loop.from_string(str(ml)))
        # Check the data too - this should never fail (the previous test would
        # have already failed.)
        self.assertEqual(ml[0][0], Loop.from_string(str(ml))[0][0])

    def test_parse_outliers(self):
        """ Make sure the parser handles edge cases. """

        parser = _Parser()
        parser.load_data("""data_#pound
save_entry_information  _Entry.Sf_category entry_information _Entry.Sf_framecode entry_information
_Entry.sameline_comment value #ignore this all
_Entry.ID    \".-!?\"
_Entry.Invalid_tag            "This tag doesn't exist."
_Entry.Title
; Solution structure of chicken villin headpiece subdomain contain;ing a fluorinated side chain in the cores;
;
_Entry.Submi#ssion_date                "check inn"er "quoted vals"
_Entry.Accession_date                 'check inner quoted vals'
_Entry.Original_NMR_STAR_version      '_.'
   _Entry.Experimental_method            $
   _Entry.Details                        "1#"
   _Entry.Experimental_method_subtype    solution
   _Entry.BMRB_internal_directory_name   ;data;
_Entry.pointer $it
_Entry.multi
;

   nothing
   to shift
;
_Entry.multi2
;

   ;
   something
   to shift
;
""")
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('data_#pound', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('save_entry_information', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_Entry.Sf_category', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('entry_information', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_Entry.Sf_framecode', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('entry_information', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_Entry.sameline_comment', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('value', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_Entry.ID', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('.-!?', '"'))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_Entry.Invalid_tag', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ("This tag doesn't exist.", '"'))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_Entry.Title', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), (" Solution structure of chicken villin headpiece subdomain"
                                                            " contain;ing a fluorinated side chain in the cores;\n",
                                                            ';'))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_Entry.Submi#ssion_date', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('check inn"er "quoted vals', '"'))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_Entry.Accession_date', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('check inner quoted vals', '\''))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_Entry.Original_NMR_STAR_version', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_.', '\''))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_Entry.Experimental_method', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('$', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_Entry.Details', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('1#', '"'))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_Entry.Experimental_method_subtype', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('solution', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_Entry.BMRB_internal_directory_name', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), (';data;', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('_Entry.pointer', ' '))
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ('$it', '$'))
        parser.get_token()
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ("\n   nothing\n   to shift\n", ';'))
        parser.get_token()
        parser.get_token()
        self.assertEqual((parser.token, parser.delimiter), ("\n;\nsomething\nto shift", ';'))

