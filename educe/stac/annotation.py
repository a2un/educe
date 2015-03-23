# Author: Eric Kow
# License: BSD3
# pylint: disable=W0232, R0903, C0103, pointless-string-statement

"""
STAC annotation conventions (re-exported in educe.stac)

STAC/Glozz annotations can be a bit confusing because for two reasons, first
that Glozz objects are used to annotate very different things; and second
that annotations are done on different stages

Stage 1 (units)

+-----------+---------------------------------------------+
| Glozz     | Uses                                        |
+===========+=============================================+
| units     | doc structure, EDUs, resources, preferences |
+-----------+---------------------------------------------+
| relations | coreference                                 |
+-----------+---------------------------------------------+
| schemas   | composite resources                         |
+-----------+---------------------------------------------+

Stage 2 (discourse)

+-----------+----------------------------------+
| Glozz     | Uses                             |
+===========+==================================+
| units     | doc structure, EDUs              |
+-----------+----------------------------------+
| relations | relation instances, coreference  |
+-----------+----------------------------------+
| schemas   | CDUs                             |
+-----------+----------------------------------+

**Units**

There is a typology of unit types worth noting:

* doc structure : type eg. `Dialogue`, `Turn`, `paragraph`
* resources     : subspans of segments (type `Resource`)
* preferences   : subspans of segments (type `Preference`)
* EDUs          : spans of text associated with a dialogue act (eg. type
  `Offer`, `Accept`) (during discourse stage, these are just type `Segment`)

**Relations**

* coreference : (type `Anaphora`)
* relation instances : links between EDUs, annotated with relation label
  (eg. type `Elaboration`, type `Contrast`, etc).  These can be further
  divided in subordinating or coordination relation instances according
  to their label

**Schemas**

* composite resources : boolean combinations of resources (eg. "sheep or ore")
* CDUs: type `Complex_discourse_unit` (discourse stage)
"""

from collections import namedtuple
import copy
import itertools
import math
import re
import warnings

from educe.annotation import Unit, Relation, Schema
import educe.glozz as glozz

STRUCTURE_TYPES = ['Turn', 'paragraph', 'dialogue', 'Dialogue']
RESOURCE_TYPES = ['default', 'Resource']
PREFERENCE_TYPES = ['Preference']

SUBORDINATING_RELATIONS = \
    ['Explanation',
     'Background',
     'Elaboration',
     'Correction',
     'Q-Elab',
     'Comment',
     'Question-answer_pair',
     'Clarification_question',
     'Acknowledgement']

COORDINATING_RELATIONS = \
    ['Result',
     'Narration',
     'Continuation',
     'Contrast',
     'Parallel',
     'Conditional',
     'Alternation']

DIALOGUE_ACTS =\
    ['Offer',
     'Counteroffer',
     'Accept',
     'Refusal',
     'Other']

_F_ADDRESSEE = 'Addressee'


def split_turn_text(text):
    """
    STAC turn texts are prefixed with a turn number and speaker
    to help the annotators
    (eg. "379: Bob: I think it's your go, Alice").

    Given the text for a turn, split the string into a prefix
    containing this turn/speaker information (eg. "379: Bob: "),
    and a body containing the turn text itself (eg. "I think it's
    your go, Alice").

    Mind your offsets! They're based on the whole turn string.
    """
    prefix_re = re.compile(r'(^[0-9]+ ?: .*? ?: )(.*)$')
    match = prefix_re.match(text)
    if match:
        return (match.group(1), match.group(2))
    else:
        # it's easy to just return the body here, but when this arises
        # it's a sign that something weird has happened
        raise Exception("Turn does not start with number/speaker prefix: "
                        + text)


def turn_id(anno):
    """
    Return as an integer the turn number associated with a turn
    annotation (or None if this information is missing).
    """
    tid_str = anno.features.get('Identifier')
    return int(tid_str) if tid_str else None


def addressees(anno):
    """
    The set of people spoken to during an edu annotation ::

        Annotation -> Set String

    Note: this returns `None` if the value is the default
    'Please choose...'; but otherwise, it preserves values
    like 'All' or '?'.
    """
    addr = anno.features.get(_F_ADDRESSEE)
    if addr is None or addr == 'Please choose...':
        return None
    else:
        return frozenset(name.strip() for name in addr.split(','))


def set_addressees(anno, addr):
    """
    Set the addresee list for an annotation.  If the value
    `None` is provided, the addressee list is deleted (if
    present) ::

        (Iterable String, Annotation) -> IO ()
    """
    feats = anno.features
    if addr is not None:
        feats[_F_ADDRESSEE] = ', '.join(sorted(addr))
    elif _F_ADDRESSEE in feats:
        del feats[_F_ADDRESSEE]


# ---------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------


RENAMES = {'Strategic_comment': 'Other',
           'Segment': 'Other'}
"Dialogue acts that should be treated as a different one"


def dialogue_act(anno):
    """
    Set of dialogue act (aka speech act) annotations for a Unit, taking into
    consideration STAC conventions like collapsing Strategic_comment into Other

    By rights should be singleton set, but there used to be more than one,
    something we want to phase out?
    """
    return frozenset(RENAMES.get(k, k) for k in split_type(anno))


def relation_labels(anno):
    """
    Set of relation labels (eg. Elaboration, Explanation),
    taking into consideration any applicable STAC-isms
    """
    renames = {}

    return frozenset(renames.get(k, k) for k in split_type(anno))


def split_type(anno):
    """
    An object's type as a (frozen)set of items.
    You're probably looking for `educe.stac.dialogue_act` instead.
    """
    return frozenset(anno.type.split("/"))


def is_resource(annotation):
    """
    See Unit typology above
    """
    return isinstance(annotation, Unit) and\
        annotation.type in RESOURCE_TYPES


def is_preference(annotation):
    """
    See Unit typology above
    """
    return isinstance(annotation, Unit) and\
        annotation.type in PREFERENCE_TYPES


def is_turn(annotation):
    """
    See Unit typology above
    """
    return isinstance(annotation, Unit) and\
        annotation.type == 'Turn'


def is_dialogue(annotation):
    """
    See Unit typology above
    """
    return isinstance(annotation, Unit) and\
        annotation.type == 'Dialogue'


def is_edu(annotation):
    """
    See Unit typology above
    """
    blacklist = STRUCTURE_TYPES + RESOURCE_TYPES + PREFERENCE_TYPES
    return isinstance(annotation, Unit) and\
        annotation.type not in blacklist


def is_relation_instance(annotation):
    """
    See Relation typology above
    """
    return isinstance(annotation, Relation) and\
        annotation.type in SUBORDINATING_RELATIONS or\
        annotation.type in COORDINATING_RELATIONS


def is_subordinating(annotation):
    """
    See Relation typology above
    """
    return isinstance(annotation, Relation) and\
        annotation.type in SUBORDINATING_RELATIONS


def is_coordinating(annotation):
    """
    See Relation typology above
    """
    return isinstance(annotation, Relation) and\
        annotation.type in COORDINATING_RELATIONS


def is_cdu(annotation):
    """
    See CDUs typology above
    """
    return isinstance(annotation, Schema) and\
        annotation.type == 'Complex_discourse_unit'


def is_dialogue_act(annotation):
    """
    Deprecated in favour of is_edu
    """
    warnings.warn("deprecated, use is_edu instead", DeprecationWarning)
    return is_edu(annotation)


def is_structure(annotation):
    """
    Is one of the document-structure annotations, something an
    annotator is expected not to edit, create, delete
    """
    return isinstance(annotation, Unit) and\
        annotation.type in STRUCTURE_TYPES


def cleanup_comments(anno):
    """
    Strip out default comment text from features.
    This placeholder text was inserted as a UI aid during editing
    in Glozz, but isn't actually the comment itself
    """
    placeholder = "Please write in remarks..."
    ckey = "Comments"
    if ckey in anno.features.keys() and anno.features[ckey] == placeholder:
        del anno.features[ckey]


def twin(corpus, anno, stage='units'):
    """
    Given an annotation in a corpus, retrieve the equivalent annotation
    (by local identifier) from a a different stage of the corpus.
    Return this "twin" annotation or None if it is not found

    Note that the annotation's origin must be set

    The typical use of this would be if you have an EDU in the 'discourse'
    stage and need to get its 'units' stage equvialent to have its
    dialogue act.

    :param twin_doc: unit-level document to fish twin from (None if you
    want educe to search for it in the corpus; NB: corpus can be None if
    you supply this)
    """
    if anno.origin is None:
        raise Exception('Annotation origin must be set')
    twin_key = copy.copy(anno.origin)
    twin_key.stage = stage
    if twin_key in corpus:
        return twin_from(corpus[twin_key], anno)
    else:
        return None


def twin_from(doc, anno):
    """
    Given a document and an annotation, return the first annotation in
    the document with a matching local identifier.
    """
    anno_local_id = anno.local_id()
    twins = [u for u in doc.annotations()
             if u.local_id() == anno_local_id]
    return twins[0] if twins else None


def speaker(anno):
    """
    Return the speaker associated with a turn annotation.
    NB: crashes if there is none
    """
    return anno.features['Emitter']


# ---------------------------------------------------------------------
# Adding annotations
# ---------------------------------------------------------------------

STAC_GLOZZ_FS_ORDER = \
    ['Status',
     'Quantity',
     'Correctness',
     'Kind',
     'Comments',
     'Developments',
     'Emitter',
     'Identifier',
     'Timestamp',
     'Resources',
     'Trades',
     'Dice_rolling',
     'Gets',
     'Has_resources',
     'Amount_of_resources',
     'Addressee',
     'Surface_act']

STAC_UNANNOTATED_FS_ORDER = \
    ['Status',
     'Quantity',
     'Correctness',
     'Kind',
     'Identifier',
     'Timestamp',
     'Emitter',
     'Resources',
     'Developments',
     'Comments',
     'Dice_rolling',
     'Gets',
     'Trades',
     'Has_resources',
     'Amount_of_resources',
     'Addressee',
     'Surface_act']

STAC_MD_ORDER = \
    ['author',
     'creation-date',
     'lastModifier',
     'lastModificationDate']

STAC_OUTPUT_SETTINGS = \
    glozz.GlozzOutputSettings(STAC_GLOZZ_FS_ORDER,
                              STAC_MD_ORDER)

STAC_UNANNOTATED_OUTPUT_SETTINGS = \
    glozz.GlozzOutputSettings(STAC_UNANNOTATED_FS_ORDER,
                              STAC_MD_ORDER)


# Deprecated
stac_output_settings = STAC_OUTPUT_SETTINGS
stac_unannotated_output_settings = STAC_UNANNOTATED_OUTPUT_SETTINGS


class PartialUnit(namedtuple("PartialUnit", "span type features")):
    """
    Partially instantiated unit, for use when you want to programmatically
    insert annotations into a document

    A partially instantiated unit does not have any metadata (creation date,
    etc); as these will be derived automatically
    """
    pass


def create_units(_, doc, author, partial_units):
    """
    Return a collection of instantiated new unit objects.

    :param partial_units:
    :type  partial_units: iterable of `PartialUnit`
    """
    # It seems like Glozz uses the creation-date metadata field to
    # identify units (symptom: units that have different ids, but
    # some date don't appear in UI).
    #
    # Also, other tools in the STAC pipeline seem to use the convention
    # of negative numbers for fields where the notion of a creation date
    # isn't very appropriate (automatically derived annotations)
    #
    # So we take the smallest negative date (largest absolute value)
    # and subtract from there.
    #
    # For readability, we'll jump up a couple powers of 10
    creation_dates = [int(u.metadata['creation-date']) for u in doc.units]
    smallest_neg_date = min(creation_dates)
    if smallest_neg_date > 0:
        smallest_neg_date = 0
    # next two power of 10
    id_base = 10 ** (int(math.log10(abs(smallest_neg_date))) + 2)

    def mk_creation_date(counter):
        "from counter to string for next available creation date"
        return str(0 - (id_base + counter))

    def mk_unit(partial, counter):
        "from PartialUnit and counter to Unit"

        # Note that Glozz seems to identify items by the pair of author and
        # creation date, ignoring the unit ID altogether (assumed to be
        # author_date)
        creation_date = mk_creation_date(counter)
        metadata = {'author': author,
                    'creation-date': creation_date,
                    'lastModifier': 'n/a',
                    'lastModificationDate': '0'}
        unit_id = '_'.join([author, str(counter)])
        return Unit(unit_id,
                    partial.span,
                    partial.type,
                    partial.features,
                    metadata)

    return [mk_unit(x, i) for x, i in
            itertools.izip(partial_units, itertools.count(0))]
