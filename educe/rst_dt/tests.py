import codecs
import glob
import os
import sys
import unittest

from educe.rst_dt import parse, transform, deptree

# ---------------------------------------------------------------------
# example tree snippets
# ---------------------------------------------------------------------

TSTR0 = """
( Root (span 5 6)
  ( Satellite (leaf 5) (rel2par act:goal) (text <EDU>x</EDU>) )
  ( Nucleus   (leaf 6) (rel2par act:goal) (text <EDU>y</EDU>) )
)
"""

TSTR1 = """
( Root (span 1 9)
  ( Nucleus (leaf 1) (rel2par textualOrganization)
                     (text <s><EDU> ORGANIZING YOUR MATERIALS </EDU></s>) )
  ( Satellite (span 2 9) (rel2par textualOrganization)
    ( Satellite (span 2 4) (rel2par general:specific)
      ( Nucleus (span 2 3) (rel2par preparation:act)
        ( Satellite (leaf 2) (rel2par preparation:act)
          (text <s><EDU> Once you've decided on the kind of paneling you want to install --- and the pattern ---</EDU>) )
        ( Nucleus (leaf 3) (rel2par preparation:act)
          (text <EDU>some preliminary steps remain</EDU>) )
      )
      ( Satellite (leaf 4) (rel2par preparation:act)
          (text <EDU>before you climb into your working clothes. </EDU></s>) )
    )
    ( Nucleus (span 5 9) (rel2par general:specific)
      ( Nucleus (span 5 8) (rel2par preparation:act)
        ( Nucleus (span 5 7) (rel2par step1:step2)
          ( Nucleus (span 5 6) (rel2par preparation:act)
            ( Satellite (leaf 5) (rel2par act:goal)
                (text <s><EDU> You'll need to measure the wall or room to be paneled,</EDU>) )
            ( Nucleus (leaf 6) (rel2par act:goal)
                (text <EDU>estimate the amount of paneling you'll need,</EDU>) )
          )
          ( Nucleus (leaf 7) (rel2par preparation:act) (text <EDU>buy the paneling,</EDU>) )
        )
        ( Nucleus (leaf 8) (rel2par step1:step2) (text <EDU>gather the necessary tools and equipment (see illustration on page 87),</EDU>) )
      )
      ( Nucleus (leaf 9) (rel2par preparation:act) (text <EDU>and even condition certain types of paneling before installation. </EDU></s>) )
    )
  )
)
"""

TEXT1 = " ".join(\
        [" ORGANIZING YOUR MATERIALS ",
         " Once you've decided on the kind of paneling you want to install "
         "--- and the pattern ---",

         "some preliminary steps remain",
         "before you climb into your working clothes. ",
         " You'll need to measure the wall or room to be paneled,",
         "estimate the amount of paneling you'll need,",
         "buy the paneling,",
         "gather the necessary tools and equipment (see illustration "
         "on page 87),",

         "and even condition certain types of paneling before installation. "
         ])


# ---------------------------------------------------------------------
#
# ---------------------------------------------------------------------


class RSTTest(unittest.TestCase):
    _trees = {}  # will be lazily populated
    longMessage = True

    def test_tstr0(self):
        parse.RSTTree.build(TSTR0)

    def test_tstr1(self):
        t = parse.RSTTree.build(TSTR1)
        t_text = t.text()
        sp = t.node.span
        self.assertEqual((1, 9), t.edu_span())
        self.assertEqual(TEXT1, t_text)
        self.assertEqual(len(t_text), sp.char_end)

    def test_from_files(self):
        for i in glob.glob('tests/*.dis'):
            t = parse.read_annotation_file(i)
            self.assertEqual(len(t.text()), t.node.span.char_end)

    def _test_trees(self):
        if not self._trees:
            self._trees = {}
            for i, tstr in enumerate([TSTR0, TSTR1]):
                self._trees["tstr%d" % i] = parse.RSTTree.build(tstr)
            for i in glob.glob('tests/*.dis'):
                bname = os.path.basename(i)
                self._trees[bname] = parse.read_annotation_file(i)
        return self._trees

    def test_binarize(self):
        for name, tree in self._test_trees().items():
            bin_tree = transform._binarize(tree)
            self.assertTrue(transform.is_binary(bin_tree))

    def test_rst_to_dt(self):
        for name, tree in self._test_trees().items():
            rst1 = transform.SimpleRSTTree.from_rst_tree(tree)
            dep = deptree.relaxed_nuclearity_to_deptree(rst1)
            rst2 = deptree.relaxed_nuclearity_from_deptree(dep, [])
            self.assertEqual(rst1.node.span,
                             rst2.node.span,
                             "span equality on " + name)
            self.assertEqual(rst1.node.edu_span,
                             rst2.node.edu_span,
                             "edu span equality on " + name)

