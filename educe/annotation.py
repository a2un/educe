# Author: Eric Kow
# License: BSD3

import collections
from   itertools import chain
import warnings

"""
Low-level representation of corpus annotations, following somewhat faithfully
the Glozz_ model for annotations.

This is low-level in the sense that we make little attempt to interpret the
information stored in these annotations. For example, a relation might claim to
link two units of id unit42 and unit43. This being a low-level representation,
we simply note the fact. A higher-level representation might attempt to
actually make the corresponding units available to you, or perhaps provide
some sort of graph representation of them

.. _Glozz: http://erickow.com/posts/anno-models-glozz.html
"""

class Span(object):
    """
    What portion of text an annotation corresponds to.
    Assumed to be in terms of character offsets
    """
    def __init__(self, start, end):
        self.char_start=start
        self.char_end=end

    def  __str__(self):
        return ('(%d,%d)' % (self.char_start, self.char_end))

    def __lt__(self, other):
        return self.char_start < other.char_start or\
            (self.char_start == other.char_start and
             self.char_end   <  other.char_end)

    def __eq__(self, other):
        return self.char_start == other.char_start and\
               self.char_end   == other.char_end

    def __gt__(self, other):
        return other < self

    def __ne__(self, other):
        return not self == other

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return other <= self

    def len(self):
        """
        Return the length of this span
        """
        return self.char_end - self.char_start

    def shift(self, offset):
        """
        Return a copy of this span, shifted to the right
        (if offset is positive) or left (if negative).

        It may be a bit more convenient to use 'absolute/relative'
        if you're trying to work with spans that are within other
        spans.
        """
        return Span(self.char_start + offset, self.char_end + offset)

    def absolute(self, other):
        """
        Assuming this span is relative to some other span,
        return a suitably shifted "absolute" copy.
        """
        return self.shift(other.char_start)

    def relative(self, other):
        """
        Assuming this span is relative to some other span,
        return a suitably shifted "absolute" copy.
        """
        return self.shift(0 - other.char_start)

    def encloses(self, sp):
        """
        Return True if this span includes the argument

        Note that `x.encloses(x) == True`

        Corner case: `x.encloses(None) == False`

        See also `educe.graph.EnclosureGraph` if you might be repeating
        these checks
        """
        if sp is None:
            return False
        else:
            return self.char_start <= sp.char_start and\
                   self.char_end   >= sp.char_end

    def overlaps(self, sp):
        """
        Return the overlapping region if two spans have regions
        in common, or else None
        """
        if sp is None:
            return None
        else:
            common_start = max(self.char_start, sp.char_start)
            common_end   = min(self.char_end,   sp.char_end)
            if common_start < common_end:
                return Span(common_start, common_end)
            else:
                return None

    def merge(self, other):
        """
        Return a span that stretches from the beginning to the
        end of the two spans. Whereas `overlaps` can be thought of
        as returning the intersection of two spans, this can be
        thought of as returning the union.
        """
        big_start = min(self.char_start, other.char_start)
        big_end = max(self.char_end, other.char_end)
        return Span(big_start, big_end)

class RelSpan(object):
    """
    Which two units a relation connections.
    """
    def __init__(self, t1, t2):
        self.t1=t1
        self.t2=t2

    def  __str__(self):
        return ('%s -> %s' % (self.t1, self.t2))

class Standoff(object):
    """
    A standoff object ultimately points to some piece of text.
    The pointing is not necessarily direct though
    """
    def __init__(self, origin=None):
        self.origin=origin

    def _members(self):
        """
        Any annotations contained within this annotation.

        Must return None if is a terminal annotation (not the same
        meaning as returning the empty list)
        """
        return None

    def _terminals(self, seen=[]):
        """
        For terminal annotations, this is just the annotation itself.
        For non-terminal annotations, this recursively fetches the
        terminals
        """
        my_members = self._members()
        if my_members is None:
            return [self]
        else:
            return chain.from_iterable([m._terminals(seen + my_members)
                                        for m in my_members if m not in seen])

    def text_span(self):
        """
        Return the span from the earliest terminal annotation contained here
        to the latest.

        Corner case: if this is an empty non-terminal (which would be a very
        weird thing indeed), return None

        NOTES:

        * the `doc` argument is deprecated
        """
        terminals = list(self._terminals())
        if len(terminals) > 0:
            start = min( [t.span.char_start for t in terminals] )
            end   = max( [t.span.char_end   for t in terminals] )
            return Span(start, end)
        else:
            return None

class Annotation(Standoff):
    """
    Any sort of annotation. Annotations tend to have

    * span:     some sort of location (what they are annotating)
    * type:     some key label (we call a type)
    * features: an attribute to value dictionary
    """
    def __init__(self, anno_id, span, type, features, metadata=None, origin=None):
        Standoff.__init__(self, origin)
        self.origin=origin
        self._anno_id=anno_id
        self.span=span
        self.type=type
        self.features=features
        self.metadata=metadata

    def __lt__(self, other):
        return self._anno_id < other._anno_id

    def __str__(self):
        feats=str(self.features)
        return ('%s [%s] %s %s' % (self.identifier(),self.type, self.span, feats))

    def local_id(self):
        """
        An identifier which is sufficient to pick out this annotation within a
        single annotation file
        """
        return self._anno_id

    def identifier(self):
        """
        String representation of an identifier that should be unique
        to this corpus at least.

        If the unit has an origin (see "FileId"), we use the

        * document
        * subdocument
        * stage
        * (but not the annotator!)
        * and the id from the XML file

        If we don't have an origin we fall back to just the id provided
        by the XML file

        See also `position` as potentially a safer alternative to this
        (and what we mean by safer)
        """
        o=self.origin
        local_id=self._anno_id
        if o is None:
            return local_id
        else:
            return o.mk_global_id(local_id)

class Unit(Annotation):
    """
    An annotation over a span of text
    """
    def __init__(self, unit_id, span, type, features, metadata=None, origin=None):
        Annotation.__init__(self, unit_id, span, type, features, metadata, origin)

    def position(self):
        """
        The position is the set of "geographical" information only to identify
        an item. So instead of relying on some sort of name, we might rely on
        its text span. We assume that some name-based elements (document name,
        subdocument name, stage) can double as being positional.

        If the unit has an origin (see "FileId"), we use the

        * document
        * subdocument
        * stage
        * (but not the annotator!)
        * and its text span

        **position vs identifier**

        This is a trade-off.  One the hand, you can see the position as being
        a safer way to identify a unit, because it obviates having to worry
        about your naming mechanism guaranteeing stability across the board
        (eg. two annotators stick an annotation in the same place; does it have
        the same name). On the *other* hand, it's a bit harder to uniquely
        identify objects that may coincidentally fall in the same span.  So
        how much do you trust your IDs?
        """
        o=self.origin
        if o is None:
            ostuff=[]
        else:
            ostuff=[o.doc, o.subdoc, o.stage]
        return ":".join(ostuff + map(str,[self.span.char_start, self.span.char_end]))

class Relation(Annotation):
    """
    An annotation between two annotations.
    Relations are directed; see `RelSpan` for details

    Use the `source` and `target` field to grab these respective
    annotations, but note that they are only instantiated after
    `fleshout` is called (when initialising a `Document`, any
    relations and schemas within are also fleshed out)
    """
    def __init__(self, rel_id, span, type, features, metadata=None):
        Annotation.__init__(self, rel_id, span, type, features, metadata)

    def _members(self):
        return [ self.source, self.target ]

    def fleshout(self, objects):
        """
        Given a dictionary mapping ids to annotation objects, set this
        relation's source and target fields.

        FIXME: Not sure if there is an idiom for two-stage object creation
        in Python. The idea here is that we first want to create a pool of
        annotation objects, and having done so, we want to add pointers
        from some of these objects to the others; so we have to "flesh"
        these objects out after creating them, but before using them.
        """
        source_span = self.span.t1
        target_span = self.span.t2
        if source_span not in objects:
            raise Exception('There is no annotation with id %s [relation source]' % source_span)
        elif target_span not in objects:
            raise Exception('There is no annotation with id %s [relation target]' % target_span)
        else:
            self.source = objects[source_span]
            self.target = objects[target_span]

class Schema(Annotation):
    """
    An annotation between a set of annotations

    Use the `members` field to grab the annotations themselves.
    But note that it is only created when `fleshout` is called.
    """
    def __init__(self, rel_id, units, relations, schemas, type, features, metadata=None):
        self.units     = units
        self.relations = relations
        self.schemas   = schemas
        member_ids     = units | relations | schemas
        Annotation.__init__(self, rel_id, member_ids, type, features, metadata)

    def terminals(self):
        """
        All unit-level annotations contained in this schema or
        (recursively in schema contained herein)
        """
        return list(self._terminals())

    def _members(self):
        return self.members

    def fleshout(self, objects):
        """
        Given a dictionary mapping ids to annotation objects, set this
        schema's `members` field to point to the appropriate objects
        """
        self.members = []
        for i in self.span:
            if i not in objects:
                raise Exception('There is no annotation with id %s [schema member]' % i)
            self.members.append(objects[i])

class Document(Standoff):
    """
    A single (sub)-document.

    This can be seen as collections of unit, relation, and schema annotations
    """
    def __init__(self, units, relations, schemas, text):
        Standoff.__init__(self, None)

        self.units=units
        self.relations=relations
        self.rels=relations # FIXME should find a way to deprecate this
        self.schemas=schemas
        objects = {}

        for i in self.units:
            objects[i.local_id()] = i
        for i in self.relations:
            objects[i.local_id()] = i
        for i in self.schemas:
            objects[i.local_id()] = i

        for x in self.relations:
            x.fleshout(objects)
        for x in self.schemas:
            x.fleshout(objects)

        self._text=text

    def annotations(self):
        """
        All annotations associated with this document
        """
        return self.units + self.relations + self.schemas

    def _members(self):
        return self.annotations()

    def fleshout(self, origin):
        """
        See `set_origin`
        """
        self.set_origin(origin)

    def set_origin(self, origin):
        """
        If you have more than one document, it's a good idea to
        set its origin to an `educe.corpus.file_id` so that you
        can more reliably the annotations apart.
        """
        self.origin = origin
        for x in self.annotations():
            x.origin = origin

    def global_id(self, local_id):
        """
        String representation of an identifier that should be unique
        to this corpus at least.
        """
        o=self.origin
        if o is None:
            return local_id
        else:
            return o.mk_global_id(local_id)

    def text(self, span=None):
        """
        Return the text associated with these annotations (or None),
        optionally limited to a span
        """
        if self._text is None:
            return None
        elif span is None:
            return self._text
        else:
            return self._text[span.char_start:span.char_end]

    def text_for(self, unit):
        """
        Return a string representing the text covered by either this document
        or unit.
        """
        warnings.warn("deprecated, use doc.text(x.text_span()) instead", DeprecationWarning)
        return self.text(unit.span)
