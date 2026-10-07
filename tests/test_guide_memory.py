import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from folio_beneficiary import recovery_steps, visible_plan, big_picture
from folio_catalog import extra_runbook, record_fields, ensure_sections
import folio_memory as memory


class GuideTests(unittest.TestCase):
    def setUp(self):
        self.plan = {'meta': {'owner': 'Example', 'planName': 'Family guide'},
                     'people': {'executor':'Known Executor'}, 'vaults': [],
                     'accessRecords': [{'kind':'EntropyLab journal','mode':'Direct access details inside encrypted guide','directAccess':'journal-only-secret','where':'Offline archive'}],
                     'instructions':[{'title':'Find the blue packet','action':'Ask the named trustee','stop':'Stop if the label differs'}]}

    def test_beneficiary_read_only_and_masked_by_default(self):
        before = copy.deepcopy(self.plan)
        hidden = '\n'.join(body for _,body in recovery_steps(self.plan))
        shown = '\n'.join(body for _,body in recovery_steps(self.plan,True))
        self.assertNotIn('journal-only-secret',hidden)
        self.assertIn('journal-only-secret',shown)
        self.assertIn('Known Executor',hidden)
        self.assertIn('Ask the named trustee',hidden)
        self.assertIn('Stop if the label differs',hidden)
        self.assertEqual(before,self.plan)
        self.assertNotIn('journal-only-secret',extra_runbook(visible_plan(self.plan)))

    def test_hint_mode_and_legacy_plan(self):
        self.plan['accessRecords'][0]['mode']='Hint only'
        fields=record_fields('accessRecords',self.plan['accessRecords'][0])
        self.assertNotIn('directAccess',[x[0] for x in fields])
        self.assertIn('journalFormat',[x[0] for x in fields])
        old={'meta':{},'people':{},'vaults':[]}
        self.assertEqual(len(recovery_steps(old)),8)
        ensure_sections(old)
        self.assertEqual(old['accessRecords'],[])
        self.assertEqual(old['instructions'],[])

    def test_big_picture_keeps_mixed_wallet_routes_distinct(self):
        plan = {'vaults': [
            {'name': 'Wallet A', 'm': 1, 'n': 1, 'coordinator': 'Software A'},
            {'name': 'Wallet B', 'm': 2, 'n': 3, 'coordinator': 'Software B'},
            {'name': 'Wallet C'}]}
        stages = big_picture(plan)
        boxes = [b for stage in stages for b in stage['boxes']]
        software = next(b for b in boxes if b['icon'] == 'laptop')
        self.assertIn('Wallet A: Software A', software['detail'])
        self.assertIn('Wallet B: Software B', software['detail'])
        self.assertIn('Wallet C: not recorded', software['detail'])
        self.assertIn('needs 1 of 1', boxes[1]['detail'])
        self.assertIn('needs 2 of 3', boxes[2]['detail'])
        self.assertIn('not recorded', boxes[3]['detail'])
        sign = next(b for b in boxes if b['icon'] == 'sign')
        self.assertIn('Each wallet', sign['detail'])
        self.assertNotIn('any 1', sign['detail'])

    def test_big_picture_derives_chain_from_plan(self):
        """The visual overview is pure presentation: stages come from recorded
        facts, gaps stay explicit, and no plan data is required to exist."""
        stages = big_picture(self.plan)  # no vaults recorded
        self.assertEqual(stages[0]['boxes'][0]['icon'], 'guide')
        self.assertIn('No wallet recorded',
                      [b['title'] for s in stages for b in s['boxes']])
        self.assertEqual([s['boxes'][0]['title'] for s in stages[-2:]],
                         ['Rebuild the wallet', 'Sign'])
        self.plan['vaults'] = [{'name': 'Multisig savings', 'm': 2, 'n': 3,
                                'coordinator': 'Sparrow',
                                'keys': [{'label': 'Coldcard A', 'medium': 'Steel / metal plate',
                                          'locations': 'home safe'},
                                         {'label': 'Jade B'}, {}]}]
        self.plan['backups'] = {'descriptorLocations': [{'where': 'bank box'}]}
        stages = big_picture(self.plan)
        gather = stages[1]
        self.assertEqual(gather['joiner'], '+')
        self.assertEqual(len(gather['boxes']), 4)  # vault box + three keys
        self.assertEqual(gather['boxes'][0]['detail'], 'needs 2 of 3 keys to spend')
        self.assertEqual(gather['boxes'][1]['detail'], 'Steel / metal plate · home safe')
        self.assertEqual(gather['boxes'][2]['detail'], 'backup and location not recorded')
        self.assertEqual(gather['boxes'][3]['title'], 'Key 3')
        titles = [b['title'] for s in stages for b in s['boxes']]
        self.assertIn('Sparrow', titles)
        self.assertIn('The wallet map', titles)
        map_box = next(b for s in stages for b in s['boxes'] if b['title'] == 'The wallet map')
        self.assertEqual(map_box['detail'], '1 recorded copy location(s)')
        sign_stage = stages[-1]
        self.assertEqual(sign_stage['joiner'], '→')
        self.assertEqual(sign_stage['boxes'][0]['detail'], 'any 2 of the 3 keys approve')
        for stage in stages:
            for box in stage['boxes']:
                self.assertTrue(box['about'], 'every box needs a plain-language explanation')


class MemoryTests(unittest.TestCase):
    def test_ram_mount_resolution(self):
        mounts={'/':{'fstype':'overlay','options':'rw,lowerdir=/ro,upperdir=/cow/upper,workdir=/cow/work'},
                '/cow/upper':{'fstype':'tmpfs','options':'rw'}}
        self.assertTrue(memory.ram_backed('/',mounts.get))
        mounts['/cow/upper']['fstype']='ext4'
        self.assertFalse(memory.ram_backed('/',mounts.get))
        self.assertFalse(memory.ram_backed('/unknown',mounts.get))
        self.assertFalse(memory.ram_backed('/',lambda _: {'fstype':'overlay','options':'upperdir=/'}))

    def test_gate_blocks_swap_persistence_and_unknown(self):
        with patch('folio_memory.platform.system',return_value='Linux'), \
             patch('folio_memory.Path.read_text',return_value='Filename\tType\tSize\tUsed\tPriority\n'), \
             patch('folio_memory.process_hardened',return_value=True), \
             patch('folio_memory.ram_backed',return_value=True):
            self.assertTrue(memory.memory_report()['safe'])
            with patch('folio_memory.Path.read_text',return_value='Filename\n/swapfile file 1000 0 -1\n'):
                self.assertFalse(memory.memory_report()['safe'])
            with patch('folio_memory.ram_backed',return_value=False):
                self.assertFalse(memory.memory_report()['safe'])
            with patch('folio_memory.process_hardened',return_value=False):
                self.assertFalse(memory.memory_report()['safe'])
            with patch('folio_memory.Path.read_text',side_effect=OSError):
                self.assertFalse(memory.memory_report()['safe'])
        with patch('folio_memory.platform.system',return_value='Darwin'):
            self.assertFalse(memory.memory_report()['safe'])

    def test_discard_drops_references_without_erase_claim(self):
        item={'hint':'family clue'}; plan={'items':[item]}
        memory.discard_plan(plan)
        self.assertEqual(plan,{})
        self.assertEqual(item,{})


if __name__=='__main__':unittest.main()
