import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from enterprise_qa.agent import run
from enterprise_qa.tools import Tools
from test_agent import SequenceModel, action, final


def clarify():
    return action('finish',{'status':'needs_clarification', 'answer':'请先说明报销类型。',
                           'citations':[], 'gaps':['报销类型']})


class EarlyFinishTests(unittest.TestCase):
    def test_early_clarification_is_rejected_then_model_can_recover(self):
        model=SequenceModel([clarify(),action('search',{'query':'报销'}),
             action('read',{'doc_id':'D01'}),final('报销期限为费用发生后30天。',answer='报销期限为30天。')])
        result=run(model,Tools.load(ROOT/'data/normal.json'),'报销期限是多少？')
        self.assertEqual(result['status'],'answered')
        self.assertEqual(result['trace'][0]['observation']['error'],'finish_requires_tool_observation')
        self.assertEqual([e['action'] for e in result['trace']],['finish','search','read','finish'])

    def test_model_receives_early_finish_rejection_as_observation(self):
        class Observe(SequenceModel):
            def decide(self,messages):
                if len(messages)>2:
                    self.observed=messages[-1]['content']
                return super().decide(messages)
        model=Observe([clarify(),action('search',{'query':'报销'})])
        result=run(model,Tools.load(ROOT/'data/normal.json'),'报销期限是多少？',max_steps=2)
        self.assertIn('finish_requires_tool_observation',model.observed)
        self.assertEqual(result['status'],'incomplete')

    def test_search_hit_cannot_be_skipped_before_clarification(self):
        model=SequenceModel([action('search',{'query':'报销'}),clarify()])
        result=run(model,Tools.load(ROOT/'data/normal.json'),'报销期限是多少？',max_steps=2)
        self.assertEqual(result['status'],'incomplete')
        self.assertEqual(result['trace'][-1]['observation']['error'],'read_search_candidates_before_finishing')

    def test_unsupported_initial_insufficient_evidence_is_rejected(self):
        model=SequenceModel([action('finish',{'status':'insufficient_evidence','answer':'无资料',
                            'citations':[],'gaps':['制度原文']})])
        result=run(model,Tools.load(ROOT/'data/normal.json'),'报销',max_steps=1)
        self.assertEqual(result['status'],'incomplete')
        self.assertEqual(result['trace'][0]['observation']['error'],'finish_requires_tool_observation')

    def test_unread_conflict_candidate_prevents_definitive_answer(self):
        model=SequenceModel([action('search',{'query':'报销'}),action('read',{'doc_id':'D01'}),
                             final('报销期限为费用发生后30天。')])
        result=run(model,Tools.load(ROOT/'data/documents.json'),'报销',max_steps=3)
        self.assertEqual(result['status'],'incomplete')
        self.assertEqual(result['trace'][-1]['observation']['error'],'unread_search_candidates')
        self.assertEqual(result['trace'][-1]['observation']['doc_ids'],['D02'])

    def test_genuinely_missing_topic_can_clarify_without_citations_after_lookup(self):
        model=SequenceModel([action('search',{'query':'期限'}),action('read',{'doc_id':'D01'}),clarify()])
        result=run(model,Tools.load(ROOT/'data/normal.json'),'期限是多久？')
        self.assertEqual(result['status'],'needs_clarification')
        self.assertFalse(result['citations'])

if __name__=='__main__':
    unittest.main()
