import json
import os
import sys
from csv import reader as csv_reader, writer as csv_writer
from copy import deepcopy
from itertools import chain

try:
    import entry
    import utils
    import parser as parsermod
except ImportError:
    from . import entry
    from . import utils
    from . import parser as parsermod


class Loop(object):
    """A BMRB loop object. Create using the class methods, see below."""

    def __eq__(self, other):
        """Returns True if this loop is equal to another loop, False if
        it is different."""

        return len(self.compare(other)) == 0

    def __ne__(self, other):
        """It isn't enough to define __eq__ in python2.x."""

        return not self.__eq__(other)

    def __getitem__(self, item):
        """Get the indicated row from the data array."""

        try:
            return self.data[item]
        except TypeError:
            if isinstance(item, tuple):
                item = list(item)
            return self.get_tag(tags=item)

    def __init__(self, **kwargs):
        """ You should not directly instantiate a Loop using this method.
            Instead use the class methods:
              Loop.from_scratch()
              Loop.from_string()
              Loop.from_template()
              Loop.from_file()
              Loop.from_json()"""

        # Initialize our local variables
        self.tags = []
        self.data = []
        self.category = None
        self.source = "unknown"

        star_buffer = ""

        # Update our source if it provided
        if 'source' in kwargs:
            self.source = kwargs['source']

        # Update our category if provided
        if 'category' in kwargs:
            self.category = utils.format_category(kwargs['category'])
            return

        # They initialized us wrong
        if len(kwargs) == 0:
            raise ValueError("You should not directly instantiate a Loop using "
                             "this method. Instead use the class methods: "
                             "Loop.from_scratch(), Loop.from_string(), "
                             "Loop.from_template(), Loop.from_file(), and "
                             "Loop.from_json().")

        # Parsing from a string
        if 'the_string' in kwargs:
            # Parse from a string by wrapping it in StringIO
            star_buffer = utils.StringIO(kwargs['the_string'])
            self.source = "from_string()"
        # Parsing from a file
        elif 'file_name' in kwargs:
            star_buffer = utils.interpret_file(kwargs['file_name'])
            self.source = "from_file('%s')" % kwargs['file_name']
        # Creating from template (schema)
        elif 'tag_prefix' in kwargs:

            tags = Loop._get_tags_from_schema(kwargs['tag_prefix'],
                                              all_tags=kwargs['all_tags'],
                                              schema=kwargs['schema'])
            for tag in tags:
                self.add_tag(tag)

            return

        # If we are reading from a CSV file, go ahead and parse it
        if 'csv' in kwargs and kwargs['csv']:
            csv_file = csv_reader(star_buffer)
            self.add_tag(next(csv_file))
            for row in csv_file:
                self.add_data(row)
            self.source = "from_csv('%s')" % kwargs['csv']
            return

        tmp_entry = entry.Entry.from_scratch(0)

        # Load the BMRB entry from the file
        star_buffer = utils.StringIO("data_0 save_internaluseyoushouldntseethis_frame"
                                     " _internal.use internal " + star_buffer.read() +
                                     " save_")
        parser = parsermod.Parser(entry_to_parse_into=tmp_entry)
        parser.parse(star_buffer.read(), source=self.source)

        # Check that there was only one loop here
        if len(tmp_entry[0].loops) > 1:
            raise ValueError("You attempted to parse one loop but the source "
                             "you provided had more than one loop. Please "
                             "either parse all loops as a saveframe or only "
                             "parse one loop. Loops detected:"
                             " " + str(tmp_entry[0].loops))

        # Copy the first parsed saveframe into ourself
        self.tags = tmp_entry[0][0].tags
        self.data = tmp_entry[0][0].data
        self.category = tmp_entry[0][0].category

    def __len__(self):
        """Return the number of rows of data."""

        return len(self.data)

    def __lt__(self, other):
        """Returns True if this loop sorts lower than the compared
        loop, false otherwise."""

        return self.category < other.category

    def __repr__(self):
        """Returns a description of the loop."""

        if utils.ALLOW_V2_ENTRIES and self.category is None:
            common = os.path.commonprefix(self.tags)
            if common.endswith("_"):
                common = common[:-1]
            if common == "":
                common = "Unknown"
            return "<pynmrstar.Loop '%s'>" % common
        else:
            return "<pynmrstar.Loop '%s'>" % self.category

    def __setitem__(self, key, item):
        """Set all of the instances of a tag to the provided value.
        If there are 5 rows of data in the loop, you will need to
        assign a list with 5 elements."""

        tag = utils.format_tag(key)

        # Check that their tag is in the loop
        if tag not in self.tags:
            raise ValueError("Cannot assign to tag '%s' as it does not exist "
                             "in this loop." % key)

        # Determine where to assign
        tag_id = self.tags.index(tag)

        # Make sure they provide a list of the correct length
        if len(self[key]) != len(item):
            raise ValueError("To assign to a tag you must provide a list (or "
                             "iterable) of a length equal to the number of "
                             "values that currently exist for that tag. The tag"
                             " '%s' current has %d values and you supplied "
                             "%d values." % (key, len(self[key]), len(item)))

        # Do the assignment
        for pos, row in enumerate(self.data):
            row[tag_id] = item[pos]

    def __str__(self):
        """Returns the loop in STAR format as a string."""

        # Check if there is any data in this loop
        if len(self.data) == 0:
            # They do not want us to print empty loops
            if utils.SKIP_EMPTY_LOOPS:
                return ""
            else:
                # If we have no tags than return the empty loop
                if len(self.tags) == 0:
                    return "\n   loop_\n\n   stop_\n"

        if len(self.tags) == 0:
            raise ValueError("Impossible to print data if there are no "
                             "associated tags. Loop: '%s'." % self.category)

        # Make sure the tags and data match
        self._check_tags_match_data()

        # Start the loop
        ret_string = "\n   loop_\n"
        # Print the tags
        format_string = "      %-s\n"

        # Check to make sure our category is set
        if self.category is None and not utils.ALLOW_V2_ENTRIES:
            raise ValueError("The category was never set for this loop. Either "
                             "add a tag with the category intact, specify it"
                             " when generating the loop, or set it using "
                             "set_category.")

        # Print the categories
        if self.category is None:
            for tag in self.tags:
                ret_string += format_string % tag
        else:
            for tag in self.tags:
                ret_string += format_string % (self.category + "." + tag)

        ret_string += "\n"

        row_strings = []

        if len(self.data) != 0:

            # Make a copy of the data
            working_data = []
            # Put quotes as needed on the data
            for datum in self.data:
                working_data.append([utils.clean_value(x) for x in datum])

            # The nightmare below creates a list of the maximum length of
            #  elements in each tag in the self.data matrix. Don't try to
            #   understand it. It's an incomprehensible list comprehension.
            title_widths = [max([len(str(x)) + 3 for x in col]) for
                            col in [[row[x] for row in working_data] for
                                    x in range(0, len(working_data[0]))]]

            # TODO: Replace with a smarter title_widths algorithm - or in C
            # It needs to not count the length of items that will go on their
            # own line...

            # Generate the format string
            format_string = "     " + "%-*s" * len(self.tags) + " \n"

            # Print the data, with the tags sized appropriately
            for datum in working_data:
                for pos, item in enumerate(datum):
                    if "\n" in item:
                        datum[pos] = "\n;\n%s;\n" % item

                # Print the data (combine the tags' widths with their data)
                tag_width_list = [d for d in zip(title_widths, datum)]
                row_strings.append(format_string % tuple(chain.from_iterable(tag_width_list)))

        # Close the loop
        ret_string += "".join(row_strings) + "\n   stop_\n"
        return ret_string

    @property
    def empty(self):
        """ Check if the loop has no data. """

        for row in self.data:
            for col in row:
                if col not in [None, '', '.', '?']:
                    return False

        return True

    @classmethod
    def from_file(cls, the_file, csv=False):
        """Create a saveframe by loading in a file. Specify csv=True if
        the file is a CSV file. If the_file starts with http://,
        https://, or ftp:// then we will use those protocols to attempt
        to open the file."""

        return cls(file_name=the_file, csv=csv)

    @classmethod
    def from_json(cls, json_dict):
        """Create a loop from JSON (serialized or unserialized JSON)."""

        # If they provided a string, try to load it using JSON
        if not isinstance(json_dict, dict):
            try:
                json_dict = json.loads(json_dict)
            except (TypeError, ValueError):
                raise ValueError("The JSON you provided was neither a Python "
                                 "dictionary nor a JSON string.")

        # Make sure it has the correct keys
        for check in ['tags', 'category', 'data']:
            if check not in json_dict:
                raise ValueError("The JSON you provide must be a dictionary and"
                                 " must contain the key '%s' - even if the key "
                                 "points to None." % check)

        # Create a loop from scratch and populate it
        ret = Loop.from_scratch()
        ret.tags = json_dict['tags']
        ret.category = json_dict['category']
        ret.data = json_dict['data']
        ret.source = "from_json()"

        # Return the new loop
        return ret

    @classmethod
    def from_scratch(cls, category=None, source="from_scratch()"):
        """Create an empty saveframe that you can programatically add
        to. You may also pass the tag prefix as the second argument. If
        you do not pass the tag prefix it will be set the first time you
        add a tag."""

        return cls(category=category, source=source)

    @classmethod
    def from_string(cls, the_string, csv=False):
        """Create a saveframe by parsing a string. Specify csv=True is
        the string is in CSV format and not NMR-STAR format."""

        return cls(the_string=the_string, csv=csv)

    @classmethod
    def from_template(cls, tag_prefix, all_tags=False, schema=None):
        """ Create a loop that has all of the tags from the schema present.
        No values will be assigned. Specify the tag prefix of the loop.

        The optional argument all_tags forces all tags to be included
        rather than just the mandatory tags."""

        return cls(tag_prefix=tag_prefix, all_tags=all_tags,
                   schema=schema, source="from_template()")

    @staticmethod
    def _get_tags_from_schema(category, schema=None, all_tags=False):
        """ Returns the tags from the schema for the category of this
        loop. """

        schema = utils.get_schema(schema)

        # Put the _ on the front for them if necessary
        if not category.startswith("_"):
            category = "_" + category
        if not category.endswith("."):
            category = category + "."

        tags = []

        for item in schema.schema_order:
            # The tag is in the loop
            if item.lower().startswith(category.lower()):

                # Unconditional add
                if all_tags:
                    tags.append(item)
                # Conditional add
                else:
                    if schema.schema[item.lower()]["public"] != "I":
                        tags.append(item)
        if len(tags) == 0:
            raise ValueError("The tag prefix '%s' has no corresponding tags"
                             " in the dictionary." % category)

        return tags

    def _tag_index(self, tag_name):
        """ Helper method to do a case-insensitive check for the presence
        of a given tag in this loop. Returns the index of the tag if found
        and None if not found."""

        try:
            lc_col = [x.lower() for x in self.tags]
            return lc_col.index(utils.format_tag(str(tag_name)).lower())
        except ValueError:
            return None

    def _check_tags_match_data(self):
        """ Ensures that each row of the data has the same number of
        elements as there are tags for the loop. This is necessary to
        print or do some other operations on loops that count on the values
        matching. """

        # Make sure that if there is data, it is the same width as the
        #  tag names
        if len(self.data) > 0:
            for row in self.data:
                if len(self.tags) != len(row):
                    raise ValueError("The number of tags must match the "
                                     "width of the data. Loop: '%s'." %
                                     self.category)

    def add_column(self, name, ignore_duplicates=False, update_data=False):
        """ Depreciated, please use add_tag() instead. """

        sys.stderr.write("NOTICE: add_column() is depreciated. Please use"
                         " add_tag() instead.\n")
        return self.add_tag(name, ignore_duplicates, update_data)

    def add_data(self, the_list, rearrange=False):
        """Add a list to the data field. Items in list can be any type,
        they will be converted to string and formatted correctly. The
        list must have the same cardinality as the tag names or you
        must set the rearrange variable to true and have already set all
        the tag names in the loop. Rearrange will break a longer list into
        rows based on the number of tags."""

        # Add one row of data
        if not rearrange:
            if len(the_list) != len(self.tags):
                raise ValueError("The list must have the same number of "
                                 "elements as the number of tags! Insert "
                                 "tag names first.")
            # Add the user data
            self.data.append(the_list)
            return

        # Break their data into chunks based on the number of tags
        processed_data = [the_list[x:x + len(self.tags)] for
                          x in range(0, len(the_list), len(self.tags))]
        if len(processed_data[-1]) != len(self.tags):
            raise ValueError("The number of data elements in the loop %s"
                             " does not match the number of tags!" %
                             self.category)

        # Auto convert datatypes if option set
        if utils.CONVERT_DATATYPES:
            tschem = utils.get_schema()
            for row in processed_data:
                for tag_id, datum in enumerate(row):
                    row[tag_id] = tschem.convert_tag(self.category + "." +
                                                     self.tags[tag_id],
                                                     datum,
                                                     line_num="Loop %s" %
                                                              self.category)

        self.data = processed_data

    def add_data_by_column(self, column_id, value):
        """ Depreciated, please use add_data_by_tag() instead. """

        sys.stderr.write("NOTICE: add_data_by_column() is depreciated. Please "
                         " use add_data_by_tag() instead.\n")
        return self.add_data_by_tag(column_id, value)

    def add_data_by_tag(self, tag_id, value):
        """Add data to the loop one element at a time, based on tag.
        Useful when adding data from SANS parsers."""

        # Make sure the category matches - if provided
        if "." in tag_id:
            supplied_category = utils.format_category(str(tag_id))
            if supplied_category.lower() != self.category.lower():
                raise ValueError("Category provided in your tag '%s' does "
                                 "not match this loop's category '%s'." %
                                 (supplied_category, self.category))

        pos = self._tag_index(tag_id)
        if pos is None:
            raise ValueError("The tag '%s' to which you are attempting "
                             "to add data does not yet exist. Create the "
                             "tags before adding data." % tag_id)
        if len(self.data) == 0:
            self.data.append([])
        if len(self.data[-1]) == len(self.tags):
            self.data.append([])
        if len(self.data[-1]) != pos:
            raise ValueError("You cannot add data out of tag order.")
        self.data[-1].append(value)

    def add_tag(self, name, ignore_duplicates=False, update_data=False):
        """Add a tag to the tag name list. Does a bit of validation
        and parsing. Set ignore_duplicates to true to ignore attempts
        to add the same tag more than once rather than raise an
        exception.

        You can also pass a list of tag names to add more than one
        tag at a time.

        Adding a tag will update the data array to match by adding
        None values to the rows if you specify update_data=True."""

        # If they have passed multiple tags to add, call ourself
        #  on each of them in succession
        if isinstance(name, (list, tuple)):
            for item in name:
                self.add_tag(item, ignore_duplicates=ignore_duplicates,
                             update_data=update_data)
            return

        name = name.strip()

        if "." in name:
            if name[0] != ".":
                category = name[0:name.index(".")]
                if category[:1] != "_":
                    category = "_" + category

                if self.category is None:
                    self.category = category
                elif self.category.lower() != category.lower():
                    raise ValueError("One loop cannot have tags with "
                                     "different categories (or tags that "
                                     "don't match the loop category)!")
                name = name[name.index(".") + 1:]
            else:
                name = name[1:]

        # Ignore duplicate tags
        if self._tag_index(name) is not None:
            if ignore_duplicates:
                return
            else:
                raise ValueError("There is already a tag with the name"
                                 " '%s'." % name)
        if "." in name:
            raise ValueError("There cannot be more than one '.' in a tag name.")
        if " " in name:
            raise ValueError("Tag names can not contain spaces.")

        # Add the tag
        self.tags.append(name)

        # Add None's to the rows of data
        if update_data:

            for row in self.data:
                row.append(None)

    def clear_data(self):
        """Erases all data in this loop. Does not erase the tag names
        or loop category."""

        self.data = []

    def compare(self, other):
        """Returns the differences between two loops as a list. Order of
        loops being compared does not make a difference on the specific
        errors detected."""

        diffs = []

        # Check if this is literally the same object
        if self is other:
            return []
        # Check if the other object is our string representation
        if isinstance(other, str):
            if str(self) == other:
                return []
            else:
                return ['String was not exactly equal to loop.']

        # We need to do this in case of an extra "\n" on the end of one tag
        if str(other) == str(self):
            return []

        # Do STAR comparison
        try:
            # Check category of loops
            if str(self.category).lower() != str(other.category).lower():
                diffs.append("\t\tCategory of loops does not match: '%s' vs "
                             "'%s'." % (self.category, other.category))

            # Check tags of loops
            if ([x.lower() for x in self.tags] !=
                    [x.lower() for x in other.tags]):
                diffs.append("\t\tLoop tag names do not match for loop with "
                             "category '%s'." % self.category)

            # No point checking if data is the same if the tag names aren't
            else:
                # Only sort the data if it is not already equal
                if self.data != other.data:

                    # Check data of loops
                    self_data = sorted(deepcopy(self.data))
                    other_data = sorted(deepcopy(other.data))

                    if self_data != other_data:
                        diffs.append("\t\tLoop data does not match for loop "
                                     "with category '%s'." % self.category)

        except AttributeError as err:
            diffs.append("\t\tAn exception occured while comparing: '%s'." %
                         err)

        return diffs

    def delete_data_by_tag_value(self, tag, value, index_tag=None):
        """Deletes all rows which contain the provided value in the
        provided tag name. If index_tag is provided, that tag is
        renumbered starting with 1. Returns the deleted rows."""

        # Make sure the category matches - if provided
        if "." in tag:
            supplied_category = utils.format_category(str(tag))
            if supplied_category.lower() != self.category.lower():
                raise ValueError("Category provided in your tag '%s' does "
                                 "not match this loop's category '%s'." %
                                 (supplied_category, self.category))

        search_tag = self._tag_index(tag)
        if search_tag is None:
            raise ValueError("The tag you provided '%s' isn't in this loop!" %
                             tag)

        deleted = []

        # Delete all rows in which the user-provided tag matched
        cur_row = 0
        while cur_row < len(self.data):
            if self.data[cur_row][search_tag] == value:
                deleted.append(self.data.pop(cur_row))
                continue
            cur_row += 1

        # Re-number if they so desire
        if index_tag is not None:
            self.renumber_rows(index_tag)

        return deleted

    def filter(self, tag_list, ignore_missing_tags=False):
        """ Returns a new loop containing only the specified tags.
        Specify ignore_missing_tags=True to bypass missing tags rather
        than raising an error."""

        result = Loop.from_scratch()
        valid_tags = []

        # If they only provide one tag make it a list
        if not isinstance(tag_list, (list, tuple)):
            tag_list = [tag_list]

        # Make sure all the tags specified exist
        for tag in tag_list:

            # Handle an invalid tag
            if self._tag_index(tag) is None:
                if not ignore_missing_tags:
                    raise ValueError("Cannot filter tag '%s' as it isn't "
                                     "present in this loop." % tag)
                continue

            valid_tags.append(tag)
            result.add_tag(tag)

        # Add the data for the tags to the new loop
        for row in self.get_data_by_tag(valid_tags):
            result.add_data(row)

        # Assign the category of the new loop
        if result.category is None:
            result.category = self.category

        return result

    def get_columns(self):
        """ Depreciated alias for get_tags() """

        sys.stderr.write("NOTICE: get_columns() is depreciated. Please use"
                         " get_tag_names() instead.\n")
        return self.get_tag_names()

    def get_data_as_csv(self, header=True, show_category=True):
        """Return the data contained in the loops, properly CSVd, as a
        string. Set header to False to omit the header. Set
        show_category to false to omit the loop category from the
        headers."""

        csv_buffer = utils.StringIO()
        cwriter = csv_writer(csv_buffer)

        if header:
            if show_category:
                cwriter.writerow(
                    [str(self.category) + "." + str(x) for x in self.tags])
            else:
                cwriter.writerow([str(x) for x in self.tags])

        for row in self.data:

            data = []
            for piece in row:
                data.append(piece)

            cwriter.writerow(data)

        csv_buffer.seek(0)
        return csv_buffer.read().replace('\r\n', '\n')

    def get_data_by_tag(self, tags=None):
        """ Identical to get_tag but wraps the results in a list even if
        only fetching one tag. Primarily exists for legacy code."""

        results = self.get_tag(tags=tags)

        if isinstance(tags, list):
            if len(tags) == 1:
                results = [results]
        elif isinstance(tags, str):
            results = [results]

        return results

    def get_json(self, serialize=True):
        """ Returns the loop in JSON format. If serialize is set to
        False a dictionary representation of the loop that is
        serializeable is returned."""

        loop_dict = {
            "category": self.category,
            "tags": self.tags,
            "data": self.data
        }

        if serialize:
            return json.dumps(loop_dict, default=utils._json_serialize)
        else:
            return loop_dict

    def get_tag_names(self):
        """ Return the tag names for this entry with the category
        included. Throws ValueError if the category was never set.

        To fetch tag values use get_tag()."""

        if not self.category:
            raise ValueError("You never set the category of this loop.")

        return [self.category + "." + x for x in self.tags]

    def get_tag(self, tags=None, whole_tag=False, dict_result=False):
        """Provided a tag name (or a list of tag names), or ordinals
        corresponding to tags, return the selected tags by row as
        a list of lists.

        If whole_tag=True return the full tag name along with the tag
        value, or if dict_result=True, as the tag key.

        If dict_result=True, return the tags as a list of dictionaries
        in which the tag value points to the tag."""

        # All tags
        if tags is None:
            return self.data
        # Turn single elements into lists
        if not isinstance(tags, list):
            tags = [tags]

        # Make a copy of the tags to fetch - don't modify the
        # list that was passed
        lower_tags = deepcopy(tags)

        # Strip the category if they provide it (also validate
        #  it during the process)
        for pos, item in enumerate([str(x) for x in lower_tags]):
            if ("." in item and
                    utils.format_category(item).lower() != self.category.lower()):
                raise ValueError("Cannot fetch data with tag '%s' because "
                                 "the category does not match the category of "
                                 "this loop '%s'." % (item, self.category))
            lower_tags[pos] = utils.format_tag(item).lower()

        # Make a lower case copy of the tags
        tags_lower = [x.lower() for x in self.tags]

        # Map tag name to tag position in list
        tag_mapping = dict(zip(reversed(tags_lower),
                               reversed(range(len(tags_lower)))))

        # Make sure their fields are actually present in the entry
        tag_ids = []
        for query in lower_tags:
            if str(query) in tag_mapping:
                tag_ids.append(tag_mapping[query])
            elif isinstance(query, int):
                tag_ids.append(query)
            else:
                if utils.ALLOW_V2_ENTRIES:
                    return []
                else:
                    raise ValueError("Could not locate the tag with name"
                                     " or ID: '%s' in loop '%s'." %
                                     (query, str(self.category)))

        # First build the tags as a list
        if not dict_result:

            # Use a list comprehension to pull the correct tags out of the rows
            if whole_tag:
                result = [[[self.category + "." + self.tags[col_id], row[col_id]]
                           for col_id in tag_ids] for row in self.data]
            else:
                result = [[row[col_id] for col_id in tag_ids] for
                          row in self.data]

            # Strip the extra list if only one tag
            if len(lower_tags) == 1:
                return [x[0] for x in result]
            else:
                return result
        # Make a dictionary
        else:
            if whole_tag:
                result = [dict((self.category + "." + self.tags[col_id], row[col_id]) for col_id in tag_ids) for
                          row in self.data]
            else:
                result = [dict((self.tags[col_id], row[col_id]) for col_id in tag_ids) for row in self.data]

        return result

    def add_missing_tags(self, schema=None, all_tags=False):
        """ Automatically adds any missing tags (according to the schema),
        sorts the tags, and renumbers the tags by ordinal. """

        self.add_tag(Loop._get_tags_from_schema(self.category, schema=schema, all_tags=all_tags),
                     ignore_duplicates=True, update_data=True)
        self.sort_tags()

        # See if we can sort the rows (in addition to tags)
        try:
            self.sort_rows("Ordinal")
        except ValueError:
            pass
        except TypeError:
            ordinal_idx = self._tag_index("Ordinal")

            # If we are in another row, assign to the previous row
            for pos, row in enumerate(self.data):
                row[ordinal_idx] = pos + 1

    def print_tree(self):
        """Prints a summary, tree style, of the loop."""

        print(repr(self))

    def renumber_rows(self, index_tag, start_value=1, maintain_ordering=False):
        """Renumber a given tag incrementally. Set start_value to
        initial value if 1 is not acceptable. Set maintain_ordering to
        preserve sequence with offset.

        E.g. 2,3,3,5 would become 1,2,2,4."""

        # Make sure the category matches
        if "." in str(index_tag):
            supplied_category = utils.format_category(str(index_tag))
            if supplied_category.lower() != self.category.lower():
                raise ValueError("Category provided in your tag '%s' does not "
                                 "match this loop's category '%s'." %
                                 (supplied_category, self.category))

        # Determine which tag ID to renumber
        renumber_tag = self._tag_index(index_tag)

        # The tag to replace in is the tag they specify
        if renumber_tag is None:
            # Or, perhaps they specified an integer to represent the tag?
            try:
                renumber_tag = int(index_tag)
            except ValueError:
                raise ValueError("The renumbering tag you provided '%s' "
                                 "isn't in this loop!" % index_tag)

        # Verify the renumbering column ID
        if renumber_tag >= len(self.tags) or renumber_tag < 0:
            raise ValueError("The renumbering tag ID you provided '%s' is "
                             "too large or too small! Valid tag ids are"
                             "0-%d." % (index_tag, len(self.tags) - 1))

        # Do nothing if we have no data
        if len(self.data) == 0:
            return

        # Make sure the tags and data match
        self._check_tags_match_data()

        if maintain_ordering:
            # If they have a string buried somewhere in the row, we'll
            #  have to restore the original values
            data_copy = deepcopy(self.data)
            offset = 0
            for pos in range(0, len(self.data)):
                try:
                    if pos == 0:
                        offset = start_value - int(self.data[0][renumber_tag])
                    new_data = int(self.data[pos][renumber_tag]) + offset
                    self.data[pos][renumber_tag] = new_data
                except ValueError:
                    self.data = data_copy
                    raise ValueError("You can't renumber a row containing "
                                     "anything that can't be coerced into an "
                                     "integer using maintain_ordering. I.e. "
                                     "what am I suppose to renumber '%s' to?" %
                                     self.data[pos][renumber_tag])

        # Simple renumbering algorithm if we don't need to maintain the ordering
        else:
            for pos in range(0, len(self.data)):
                self.data[pos][renumber_tag] = pos + start_value

    def set_category(self, category):
        """ Set the category of the loop. Useful if you didn't know the
        category at loop creation time."""

        self.category = utils.format_category(category)

    def sort_tags(self, schema=None):
        """ Rearranges the tag names and data in the loop to match the order
        from the schema. Uses the BMRB schema unless one is provided."""

        current_order = self.get_tag_names()

        # Sort the tags
        def sort_key(_):
            return utils._tag_key(_, schema=schema)

        sorted_order = sorted(current_order, key=sort_key)

        # Don't touch the data if the tags are already in order
        if sorted_order == current_order:
            return
        else:
            self.data = self.get_tag(sorted_order)
            self.tags = [utils.format_tag(x) for x in sorted_order]

    def sort_rows(self, tags, key=None):
        """ Sort the data in the rows by their values for a given tag
        or tags. Specify the tags using their names or ordinals.
        Accepts a list or an int/float. By default we will sort
        numerically. If that fails we do a string sort. Supply a
        function as key and we will order the elements based on the
        keys it provides. See the help for sorted() for more details. If
        you provide multiple tags to sort by, they are interpreted as
        increasing order of sort priority."""

        # Do nothing if we have no data
        if len(self.data) == 0:
            return

        # This will determine how we sort
        sort_ordinals = []

        if isinstance(tags, list):
            processing_list = tags
        else:
            processing_list = [tags]

        # Process their input to determine which tags to operate on
        for cur_tag in [str(x) for x in processing_list]:

            # Make sure the category matches
            if "." in cur_tag:
                supplied_category = utils.format_category(cur_tag)
                if supplied_category.lower() != self.category.lower():
                    raise ValueError("Category provided in your tag '%s' does "
                                     "not match this loop's category '%s'." %
                                     (supplied_category, self.category))

            renumber_tag = self._tag_index(cur_tag)

            # They didn't specify a valid tag
            if renumber_tag is None:
                # Perhaps they specified an integer to represent the tag?
                try:
                    renumber_tag = int(cur_tag)
                except ValueError:
                    raise ValueError("The sorting tag you provided '%s' "
                                     "isn't in this loop!" % cur_tag)

            # Verify the renumbering column ID
            if renumber_tag >= len(self.tags) or renumber_tag < 0:
                raise ValueError("The sorting tag ID you provided '%s' is "
                                 "too large or too small! Valid tag ids"
                                 " are 0-%d." % (cur_tag, len(self.tags) - 1))

            sort_ordinals.append(renumber_tag)

        # Do the sort(s)
        for tag in sort_ordinals:
            # Going through each tag, first attempt to sort as integer.
            #  Then fallback to string sort.
            try:
                if key is None:
                    tmp_data = sorted(self.data,
                                      key=lambda _, pos=tag: float(_[pos]))
                else:
                    tmp_data = sorted(self.data, key=key)
            except ValueError:
                if key is None:
                    tmp_data = sorted(self.data,
                                      key=lambda _, pos=tag: _[pos])
                else:
                    tmp_data = sorted(self.data, key=key)
            self.data = tmp_data

    def validate(self, validate_schema=True, schema=None,
                 validate_star=True, category=None):
        """Validate a loop in a variety of ways. Returns a list of
        errors found. 0-length list indicates no errors found. By
        default all validation modes are enabled.

        validate_schema - Determines if the entry is validated against
        the NMR-STAR schema. You can pass your own custom schema if desired,
        otherwise the schema will be fetched from the BMRB servers.

        validate_star - Determines if the STAR syntax checks are ran."""

        errors = []

        if validate_schema:
            # Get the default schema if we are not passed a schema
            my_schema = utils.get_schema(schema)

            # Check the data
            for row_num, row in enumerate(self.data):
                for pos, datum in enumerate(row):
                    line_no = str(row_num) + " tag " + str(pos) + " of loop"
                    if datum == "a":
                        pass
                    errors.extend(my_schema.val_type(self.category + "." +
                                                     self.tags[pos], datum,
                                                     category=category,
                                                     linenum=line_no))

        if validate_star:
            # Check for wrong data size
            num_cols = len(self.tags)
            for row_num, row in enumerate(self.data):
                # Make sure the width matches
                if len(row) != num_cols:
                    errors.append("Loop '%s' data width does not match it's "
                                  "tag width on row '%d'." %
                                  (self.category, row_num))

        return errors
