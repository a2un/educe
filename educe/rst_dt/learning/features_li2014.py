"""Partial re-implementation of the feature extraction procedure used in
[li2014text]_ for discourse dependency parsing on the RST-DT corpus.

.. [li2014text] Li, S., Wang, L., Cao, Z., & Li, W. (2014).
Text-level discourse dependency parsing.
In Proceedings of the 52nd Annual Meeting of the Association for
Computational Linguistics (Vol. 1, pp. 25-35).
http://www.aclweb.org/anthology/P/P14/P14-1003.pdf
"""

from collections import Counter
from functools import wraps
import re

from educe.internalutil import treenode
from educe.learning.keys import MagicKey
from educe.learning.util import tuple_feature, space_join
from .base import (SingleEduSubgroup, PairSubgroup,
                   BaseSingleEduKeys, BasePairKeys,
                   edu_feature,
                   on_first_unigram, on_last_unigram,
                   on_first_bigram, on_last_bigram,
                   feat_grouping, feat_id, feat_start, feat_end,
                   get_sentence, get_paragraph,
                   lowest_common_parent)


# ---------------------------------------------------------------------
# single EDU features
# ---------------------------------------------------------------------

# filter tags and tokens as in Li et al.'s parser
TT_PATTERN = r'.*[a-zA-Z_0-9].*'
TT_FILTER = re.compile(TT_PATTERN)


def ptb_tokens_feature(wrapped):
    """
    Lift a function from `[ptb_token] -> feature`
    to `single_function_input -> feature`
    """
    @wraps(wrapped)
    def inner(context, edu):
        "([ptb_token] -> f) -> ((context, edu) -> f)"
        tokens = context.ptb_tokens[edu]
        if tokens is None:
            return None
        # filter tags and tokens as in Li et al.'s parser
        tokens = [tt for tt in tokens
                  if (TT_FILTER.match(tt.word) is not None and
                      TT_FILTER.match(tt.tag) is not None)]
        return wrapped(tokens)
    return inner


# ---------------------------------------------------------------------
# single EDU features: concrete features
# ---------------------------------------------------------------------

# addSinglePOSFeature()

@ptb_tokens_feature
@on_first_unigram
def ptb_pos_tag_first(token):
    "POS tag for first PTB token in the EDU"
    return token.tag


@ptb_tokens_feature
@on_last_unigram
def ptb_pos_tag_last(token):
    "POS tag for last PTB token in the EDU"
    return token.tag


# length
@ptb_tokens_feature
def num_tokens(tokens):
    "number of distinct tokens in EDU text"
    return len(tokens)


@ptb_tokens_feature
def num_tokens_div5(tokens):
    "number of distinct tokens in EDU text divided by 5"
    return len(tokens)/5


@ptb_tokens_feature
@on_first_bigram
def ptb_pos_tag_first2(token):
    "POS tag for first two PTB tokens in the EDU"
    # note: PTB tokens may not necessarily correspond to words
    return token.tag


@ptb_tokens_feature
@on_last_bigram
def ptb_pos_tag_last2(token):
    "POS tag for last two PTB tokens in the EDU"
    # note: PTB tokens may not necessarily correspond to words
    return token.tag


# ngrams: words

@ptb_tokens_feature
@on_first_unigram
def ptb_word_first(token):
    "first PTB word in the EDU"
    return token.word


@ptb_tokens_feature
@on_last_unigram
def ptb_word_last(token):
    "last PTB word in the EDU"
    return token.word


@ptb_tokens_feature
@on_first_bigram
def ptb_word_first2(token):
    "first two PTB words in the EDU"
    return token.word


@ptb_tokens_feature
@on_last_bigram
def ptb_word_last2(token):
    "last PTB words in the EDU"
    return token.word


# sentence features

def sentence_id(current, edu):
    "id of sentence that contains edu"
    sent = get_sentence(current, edu)
    if sent is None:
        return None
    return sent.num


def num_edus_from_sent_start(current, edu):
    "distance of edu in EDUs from sentence start"
    sent = get_sentence(current, edu)
    if sent is None:
        return None
    # find all EDUs that are in the same sentence as edu
    edus = current.edus
    edus_same_sent = [e for e in edus
                      if get_sentence(current, e) == sent]
    result = edus_same_sent.index(edu)
    return result


def num_edus_to_sent_end(current, edu):
    "distance of edu in EDUs to sentence end"
    sent = get_sentence(current, edu)
    if sent is None:
        return None
    # find all EDUs that are in the same sentence as edu
    edus = current.edus
    edus_same_sent = [e for e in edus
                      if get_sentence(current, e) == sent]
    result = list(reversed(edus_same_sent)).index(edu)
    return result


def num_edus_from_para_start(current, edu):
    "distance of edu in EDUs from paragraph start"
    para = get_paragraph(current, edu)
    if para is None:
        return None
    # find all EDUs that are in the same paragraph as edu
    edus = current.edus
    edus_same_para = [e for e in edus
                      if get_paragraph(current, e) == para]
    result = edus_same_para.index(edu)
    return result


def num_edus_to_para_end(current, edu):
    "distance of edu in EDUs to paragraph end"
    para = get_paragraph(current, edu)
    if para is None:
        return None
    # find all EDUs that are in the same paragraph as edu
    edus = current.edus
    edus_same_para = [e for e in edus
                      if get_paragraph(current, e) == para]
    result = list(reversed(edus_same_para)).index(edu)
    return result


# this is lineID in (Li et al. 2014)
@edu_feature
def num_edus_from_doc_start(edu):
    "distance of edu in EDUs from document start"
    return edu.num - 1  # EDU numbers are in [1..]


def num_edus_to_doc_end(current, edu):
    "distance of edu in EDUs to document end"
    edus = current.edus
    result = list(reversed(edus)).index(edu)
    return result


# paragraph features
def paragraph_id(current, edu):
    "id of paragraph that contains edu"
    para = get_paragraph(current, edu)
    if para is None:
        return None
    return para.num


def paragraph_id_div5(current, edu):
    "id of paragraph that contains edu, div5"
    para = get_paragraph(current, edu)
    if para is None:
        return None
    return para.num / 5

# TODO: semantic similarity features


# basket features

@ptb_tokens_feature
def ptb_pos_tags_in_edu(tokens):
    "POS tag counts in an EDU (part of a basket feature)"
    return Counter(t.tag for t in tokens) if tokens is not None else None


def get_syntactic_labels(current, edu):
    "Syntactic labels for this EDU"
    result = []

    ptrees = current.ptb_trees[edu]
    if ptrees is None:
        return None
    # for each PTB tree, get the tree position of its leaves that are in the
    # EDU
    tpos_leaves_edu = ((ptree, [tpos_leaf
                                for tpos_leaf in ptree.treepositions('leaves')
                                if ptree[tpos_leaf].overlaps(edu)])
                       for ptree in ptrees)
    # for each span of syntactic leaves in this EDU
    for ptree, leaves in tpos_leaves_edu:
        tpos_parent = lowest_common_parent(leaves)
        # for each leaf between leftmost and rightmost, add its ancestors
        # up to the lowest common parent
        for leaf in leaves:
            for i in reversed(range(len(leaf))):
                tpos_node = leaf[:i]
                node = ptree[tpos_node]
                node_lbl = treenode(node)
                if tpos_node == tpos_parent:
                    result.append('top_' + node_lbl)
                    break
                else:
                    result.append(node_lbl)
    return Counter(result)


# ---------------------------------------------------------------------
# pair EDU features
# ---------------------------------------------------------------------

def gather_sparse_features(current, edu1, edu2):
    "Gather all sparse features in one (bulk) basket feature"
    result = Counter()
    # POS tags in each EDU
    pos_tags_edu1 = ptb_pos_tags_in_edu(current, edu1)
    if pos_tags_edu1 is not None:
        for k, v in pos_tags_edu1.items():
            result['POSF_'+k] = v
    pos_tags_edu2 = ptb_pos_tags_in_edu(current, edu2)
    if pos_tags_edu2 is not None:
        for k, v in pos_tags_edu2.items():
            result['POSS_'+k] = v
    # syntactic labels in each EDU
    if False:
        syn_labs_edu1 = get_syntactic_labels(current, edu1)
        if syn_labs_edu1 is not None:
            for k, v in syn_labs_edu1.items():
                result['SYNF_'+k] = v
        syn_labs_edu2 = get_syntactic_labels(current, edu2)
        if syn_labs_edu2 is not None:
            for k, v in syn_labs_edu2.items():
                result['SYNS_'+k] = v
    # this should do the trick
    return result


# ngrams: POS

@tuple_feature(space_join)
def ptb_pos_tag_first_pairs(_, cache, edu):
    "pair of the first POS in the two EDUs"
    return cache[edu]["ptb_pos_tag_first"]


# ngrams: words

@tuple_feature(space_join)
def ptb_word_first_pairs(_, cache, edu):
    "pair of the first words in the two EDUs"
    return cache[edu]["ptb_word_first"]


@tuple_feature(space_join)
def ptb_word_last_pairs(_, cache, edu):
    "pair of the last words in the two EDUs"
    return cache[edu]["ptb_word_last"]


@tuple_feature(space_join)
def ptb_word_first2_pairs(_, cache, edu):
    "pair of the first bigrams in the two EDUs"
    return cache[edu]["ptb_word_first2"]


@tuple_feature(space_join)
def ptb_word_last2_pairs(_, cache, edu):
    "pair of the last bigrams in the two EDUs"
    return cache[edu]["ptb_word_last2"]


# length

@tuple_feature(space_join)
def num_tokens_div5_pair(_, cache, edu):
    "pair of the length div 5 of the two EDUs"
    return cache[edu]["num_tokens_div5"]


def _minus_div5(nb1, nb2):
    "(nb1-nb2)/5"
    return (nb1-nb2)/5 if (nb1 is not None) and (nb2 is not None) else None


@tuple_feature(_minus_div5)
def num_tokens_diff_div5(_, cache, edu):
    "difference of EDU length div5"
    return cache[edu]["num_tokens"]


# sentence

def _same_or_not(x1, x2):
    "returns whether x1 and x2 are the same or different"
    if (x1 is None) or (x2 is None):
        return None
    elif x1 == x2:
        return 'same'
    else:
        return 'different'


@tuple_feature(_same_or_not)
def same_bad_sentence(_, cache, edu):
    "whose sentence comes first, of the two EDUs (bad segmentation)"
    return cache[edu]["sentence_id"]


# paragraph

def _who_s_first(x1, x2):
    "first if x1<x2, second if x2<x1, same if x1==x2"
    if (x1 is None) or (x2 is None):
        return None
    elif x1 == x2:
        return 'same'
    elif x1 < x2:
        return 'first'
    else:
        return 'second'


@tuple_feature(_who_s_first)
def first_paragraph(_, cache, edu):
    "Whose paragraph comes first, of the two EDUs"
    return cache[edu]["paragraph_id"]


def _minus(nb1, nb2):
    "nb1-nb2"
    return (nb1 - nb2) if (nb1 is not None) and (nb2 is not None) else None


@tuple_feature(_minus)
def num_paragraphs_between(_, cache, edu):
    "Num of paragraphs between the two EDUs"
    return cache[edu]["paragraph_id"]


def _minus_div3(nb1, nb2):
    "(nb1-nb2)/3"
    return ((nb1 - nb2) / 3 if (nb1 is not None) and (nb2 is not None)
            else None)


@tuple_feature(_minus_div3)
def num_paragraphs_between_div3(_, cache, edu):
    "Num of paragraphs between the two EDUs, div3"
    return cache[edu]["paragraph_id"]


# paragraph feats

@tuple_feature(_minus)
def offset_dif(_, cache, edu):
    "difference between the two EDUs' offset"
    return cache[edu]["num_edus_from_sent_start"]


@tuple_feature(_minus)
def rev_offset_dif(_, cache, edu):
    "difference between the two EDUs' revOffset"
    return cache[edu]["num_edus_to_sent_end"]


@tuple_feature(_minus_div3)
def offset_dif_div3(_, cache, edu):
    "difference between the two EDUs' offset, div3"
    return cache[edu]["num_edus_from_sent_start"]


@tuple_feature(_minus_div3)
def rev_offset_dif_div3(_, cache, edu):
    "difference between the two EDUs' offset, div3"
    return cache[edu]["num_edus_to_sent_end"]


@tuple_feature(space_join)
def offset_pair(_, cache, edu):
    "offset pair"
    return cache[edu]["num_edus_from_sent_start"]


@tuple_feature(space_join)
def rev_offset_pair(_, cache, edu):
    "revOffset pair"
    return cache[edu]["num_edus_to_sent_end"]


def offset_div3_pair(current, cache, edu1, edu2):
    "offset div 3 pair"
    offset1 = cache[edu1]["num_edus_from_sent_start"]
    offset2 = cache[edu2]["num_edus_from_sent_start"]
    offset1_div3 = offset1 / 3 if offset1 is not None else None
    offset2_div3 = offset2 / 3 if offset2 is not None else None
    return '{0}_{1}'.format(offset1_div3, offset2_div3)


def rev_offset_div3_pair(current, cache, edu1, edu2):
    "revOffset div 3 pair"
    rev_offset1 = cache[edu1]["num_edus_to_sent_end"]
    rev_offset2 = cache[edu2]["num_edus_to_sent_end"]
    rev_offset1_div3 = rev_offset1 / 3 if rev_offset1 is not None else None
    rev_offset2_div3 = rev_offset2 / 3 if rev_offset2 is not None else None
    return '{0}_{1}'.format(rev_offset1_div3, rev_offset2_div3)


def line_id_dif(current, cache, edu1, edu2):
    "difference between lineIDs"
    line_id1 = num_edus_from_doc_start(current, edu1)
    line_id2 = num_edus_from_doc_start(current, edu2)
    return line_id1 - line_id2


@tuple_feature(_minus)
def sentence_id_dif(_, cache, edu):
    "Number of sentences between the two EDUs"
    return cache[edu]["sentence_id"]


@tuple_feature(_minus_div3)
def sentence_id_dif_div3(_, cache, edu):
    "Number of sentences between the two EDUs div3"
    return cache[edu]["sentence_id"]


@tuple_feature(_minus)
def rev_sentence_id_dif(_, cache, edu):
    "Difference of rev_sentence_id of the two EDUs"
    return cache[edu]["num_edus_to_para_end"]


@tuple_feature(_minus_div3)
def rev_sentence_id_dif_div3(_, cache, edu):
    "Difference of rev_sentence_id of the two EDUs div3"
    return cache[edu]["num_edus_to_para_end"]


# ---------------------------------------------------------------------
# single EDU key groups
# ---------------------------------------------------------------------

class SingleEduSubgroup_Meta(SingleEduSubgroup):
    """
    Basic EDU-identification features
    """

    _features = [
        MagicKey.meta_fn(feat_id),
        MagicKey.meta_fn(feat_start),
        MagicKey.meta_fn(feat_end)
    ]

    def __init__(self):
        desc = self.__doc__.strip()
        super(SingleEduSubgroup_Meta, self).__init__(desc, self._features)


class SingleEduSubgroup_Syntax(SingleEduSubgroup):
    """
    syntactic features for the EDU
    """
    _features = [
        # MagicKey.discrete_fn(get_syntactic_labels)
    ]

    def __init__(self):
        desc = self.__doc__.strip()
        super(SingleEduSubgroup_Syntax, self).__init__(desc, self._features)


class SingleEduSubgroup_Pos(SingleEduSubgroup):
    """
    POS features for the EDU
    """
    _features = [
        # POS feats
        MagicKey.discrete_fn(ptb_pos_tag_first),
        MagicKey.discrete_fn(ptb_pos_tag_last),
        # MagicKey.basket_fn(ptb_pos_tags_in_edu)
    ]

    def __init__(self):
        desc = self.__doc__.strip()
        super(SingleEduSubgroup_Pos, self).__init__(desc, self._features)


class SingleEduSubgroup_Sentence(SingleEduSubgroup):
    """
    Sentence features for the EDU
    """
    _features = [
        MagicKey.continuous_fn(num_edus_from_sent_start),  # offset
        MagicKey.continuous_fn(num_edus_to_sent_end),  # revOffset
        MagicKey.continuous_fn(sentence_id),  # sentenceID
        MagicKey.continuous_fn(num_edus_to_para_end),  # revSentenceID (!?!)
    ]

    def __init__(self):
        desc = self.__doc__.strip()
        super(SingleEduSubgroup_Sentence, self).__init__(desc, self._features)


class SingleEduSubgroup_Length(SingleEduSubgroup):
    """
    Sentence features for the EDU
    """
    _features = [
        MagicKey.continuous_fn(num_tokens),
        MagicKey.continuous_fn(num_tokens_div5)
    ]

    def __init__(self):
        desc = self.__doc__.strip()
        super(SingleEduSubgroup_Length, self).__init__(desc, self._features)


class SingleEduSubgroup_Word(SingleEduSubgroup):
    """
    word features for the EDU
    """
    _features = [
        MagicKey.discrete_fn(ptb_word_first),
        MagicKey.discrete_fn(ptb_word_last),
        MagicKey.discrete_fn(ptb_word_first2),
        MagicKey.discrete_fn(ptb_word_last2),
    ]

    def __init__(self):
        desc = self.__doc__.strip()
        super(SingleEduSubgroup_Word, self).__init__(desc, self._features)


class SingleEduSubgroup_Para(SingleEduSubgroup):
    """
    paragraph features for the EDU
    """
    _features = [
        MagicKey.discrete_fn(paragraph_id),
        MagicKey.discrete_fn(paragraph_id_div5)
    ]

    def __init__(self):
        desc = self.__doc__.strip()
        super(SingleEduSubgroup_Para, self).__init__(desc, self._features)


# ---------------------------------------------------------------------
# EDU pairs
# ---------------------------------------------------------------------

class PairSubgroup_Core(PairSubgroup):
    "core features"

    _features = [
        MagicKey.meta_fn(feat_grouping)
    ]

    def __init__(self):
        desc = self.__doc__.strip()
        super(PairSubgroup_Core, self).__init__(desc, self._features)


class PairSubgroup_Word(PairSubgroup):
    "word tuple features"

    _features = [
        MagicKey.discrete_fn(ptb_word_first_pairs),
        MagicKey.discrete_fn(ptb_word_last_pairs),
        MagicKey.discrete_fn(ptb_word_first2_pairs),
        MagicKey.discrete_fn(ptb_word_last2_pairs)
    ]

    def __init__(self, inputs, sf_cache):
        self.corpus = inputs.corpus
        self.sf_cache = sf_cache
        desc = self.__doc__.strip()
        super(PairSubgroup_Word, self).__init__(desc, self._features)

    def fill(self, current, edu1, edu2, target=None):
        vec = self if target is None else target
        for key in self.keys:
            vec[key.name] = key.function(current, self.sf_cache, edu1, edu2)


class PairSubgroup_Pos(PairSubgroup):
    "POS tuple features"

    _features = [
        MagicKey.discrete_fn(ptb_pos_tag_first_pairs)
    ]

    def __init__(self, inputs, sf_cache):
        self.corpus = inputs.corpus
        self.sf_cache = sf_cache
        desc = self.__doc__.strip()
        super(PairSubgroup_Pos, self).__init__(desc, self._features)

    def fill(self, current, edu1, edu2, target=None):
        vec = self if target is None else target
        for key in self.keys:
            vec[key.name] = key.function(current, self.sf_cache, edu1, edu2)


class PairSubgroup_Para(PairSubgroup):
    "Paragraph tuple features"

    _features = [
        MagicKey.discrete_fn(first_paragraph),
        MagicKey.discrete_fn(num_paragraphs_between),
        MagicKey.discrete_fn(num_paragraphs_between_div3)
    ]

    def __init__(self, inputs, sf_cache):
        self.corpus = inputs.corpus
        self.sf_cache = sf_cache
        desc = self.__doc__.strip()
        super(PairSubgroup_Para, self).__init__(desc, self._features)

    def fill(self, current, edu1, edu2, target=None):
        vec = self if target is None else target
        for key in self.keys:
            vec[key.name] = key.function(current, self.sf_cache, edu1, edu2)


class PairSubgroup_Sent(PairSubgroup):
    "Sentence tuple features"

    _features = [
        MagicKey.discrete_fn(offset_dif),
        MagicKey.discrete_fn(rev_offset_dif),
        MagicKey.discrete_fn(offset_dif_div3),
        MagicKey.discrete_fn(rev_offset_dif_div3),
        MagicKey.discrete_fn(offset_pair),
        MagicKey.discrete_fn(rev_offset_pair),
        MagicKey.discrete_fn(offset_div3_pair),
        MagicKey.discrete_fn(rev_offset_div3_pair),
        MagicKey.discrete_fn(line_id_dif),  # !?! what's this?
        MagicKey.discrete_fn(same_bad_sentence),
        MagicKey.discrete_fn(sentence_id_dif),
        MagicKey.discrete_fn(sentence_id_dif_div3),
        MagicKey.discrete_fn(rev_sentence_id_dif),
        MagicKey.discrete_fn(rev_sentence_id_dif_div3),
    ]

    def __init__(self, inputs, sf_cache):
        self.corpus = inputs.corpus
        self.sf_cache = sf_cache
        desc = self.__doc__.strip()
        super(PairSubgroup_Sent, self).__init__(desc, self._features)

    def fill(self, current, edu1, edu2, target=None):
        vec = self if target is None else target
        for key in self.keys:
            vec[key.name] = key.function(current, self.sf_cache, edu1, edu2)


class PairSubgroup_Length(PairSubgroup):
    "Sentence tuple features"

    _features = [
        MagicKey.discrete_fn(num_tokens_div5_pair),
        MagicKey.discrete_fn(num_tokens_diff_div5)
    ]

    def __init__(self, inputs, sf_cache):
        self.corpus = inputs.corpus
        self.sf_cache = sf_cache
        desc = self.__doc__.strip()
        super(PairSubgroup_Length, self).__init__(desc, self._features)

    def fill(self, current, edu1, edu2, target=None):
        vec = self if target is None else target
        for key in self.keys:
            vec[key.name] = key.function(current, self.sf_cache, edu1, edu2)


class PairSubgroup_Basket(PairSubgroup):
    """
    Sparse features
    """
    _features = [
        MagicKey.basket_fn(gather_sparse_features)
    ]

    def __init__(self):
        desc = self.__doc__.strip()
        super(PairSubgroup_Basket, self).__init__(desc, self._features)


# export feat groups
class SingleEduKeys(BaseSingleEduKeys):
    """Single EDU features"""

    def __init__(self, inputs):
        groups = [
            SingleEduSubgroup_Meta(),
            SingleEduSubgroup_Word(),
            SingleEduSubgroup_Pos(),
            # SingleEduSubgroup_Syntax(),  # basket feature
            SingleEduSubgroup_Length(),
            SingleEduSubgroup_Para(),
            SingleEduSubgroup_Sentence()
        ]
        # if inputs.debug:
        #     groups.append(SingleEduSubgroup_Debug())
        super(SingleEduKeys, self).__init__(inputs, groups)


class PairKeys(BasePairKeys):
    """Features on a pair of EDUs"""

    def __init__(self, inputs, sf_cache=None):
        groups = [
            # meta
            PairSubgroup_Core(),
            # feature type: 1
            PairSubgroup_Word(inputs, sf_cache),
            # 2
            PairSubgroup_Pos(inputs, sf_cache),
            # 3
            PairSubgroup_Para(inputs, sf_cache),
            PairSubgroup_Sent(inputs, sf_cache),
            # 4
            PairSubgroup_Length(inputs, sf_cache),
            # 5
            # PairSubgroup_Syntax(),  # cf. basket
            # 6
            # PairSubgroup_Semantics(),
            PairSubgroup_Basket()  # basket feats for POS and syntax
        ]
        # if inputs.debug:
        #     groups.append(PairSubgroup_Debug())
        super(PairKeys, self).__init__(inputs, groups, sf_cache)

    def init_single_features(self, inputs):
        """Init features defined on single EDUs"""
        return SingleEduKeys(inputs)
