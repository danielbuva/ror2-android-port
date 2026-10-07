import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lab'))
from common import write
from integrated_objective import retain_support_roots
from build import validate_runtime_support


class ComposedSupportTests(unittest.TestCase):
 def test_ui_extension_retains_inherited_provider_and_one_bundle_owner(self):
  inherited='Assets/LabLoadingScene/MoonClosure/PillarIndicator.prefab'
  added='Assets/LabLoadingScene/ObjectiveClosure/FeatherEffect.prefab'
  recipe={'objectiveSupportAssets':[inherited], 'prefabAssets':[inherited,added,'Assets/LabLoadingScene/Hud.prefab']}
  extended=retain_support_roots(recipe,[added,added.lower()])
  self.assertEqual({x.casefold() for x in extended['objectiveSupportAssets']},{inherited.casefold(),added.casefold()})
  self.assertEqual(extended['prefabAssets'],['Assets/LabLoadingScene/Hud.prefab'])
  self.assertEqual(recipe['objectiveSupportAssets'],[inherited])

 def test_missing_inherited_provider_rejected_before_editor_dispatch(self):
  with tempfile.TemporaryDirectory() as directory:
   project=Path(directory)
   path='assets/labloadingscene/moonclosure/pillarindicator.prefab'
   write(project/'Assets/LabLoadingScene/Resources/MovementBatchProbe.json',{'objectiveSupportAssets':[path]})
   with self.assertRaisesRegex(RuntimeError,'Runtime objective support omitted'):
    validate_runtime_support(project,{'objectiveSupportAssets':[]})
   validate_runtime_support(project,{'objectiveSupportAssets':[path.upper()]})

 def test_legacy_project_without_runtime_support_remains_usable(self):
  with tempfile.TemporaryDirectory() as directory:
   validate_runtime_support(Path(directory),{})

 def test_effect_owners_match_unity_lowercase_bundle_paths(self):
  with tempfile.TemporaryDirectory() as directory:
   project=Path(directory)
   shared='Assets/LabLoadingScene/SharedEffect.prefab'
   character='Assets/LabLoadingScene/CharacterEffect.prefab'
   write(project/'Assets/LabLoadingScene/Resources/MovementBatchProbe.json',{'objectiveSupportAssets':[shared],'objectiveEffectAssets':[shared.lower(),character.lower()]})
   validate_runtime_support(project,{'objectiveSupportAssets':[shared],'prefabAssets':[character]})

 def test_missing_effect_owner_rejected_before_editor_dispatch(self):
  with tempfile.TemporaryDirectory() as directory:
   project=Path(directory)
   write(project/'Assets/LabLoadingScene/Resources/MovementBatchProbe.json',{'objectiveEffectAssets':['Assets/LabLoadingScene/UnownedEffect.prefab']})
   with self.assertRaisesRegex(RuntimeError,'effect has no explicit bundle owner'):
    validate_runtime_support(project,{'objectiveSupportAssets':[],'prefabAssets':[]})

 def test_duplicate_effect_bundle_ownership_rejected(self):
  with tempfile.TemporaryDirectory() as directory:
   project=Path(directory)
   shared='Assets/LabLoadingScene/SharedEffect.prefab'
   write(project/'Assets/LabLoadingScene/Resources/MovementBatchProbe.json',{'objectiveSupportAssets':[shared]})
   with self.assertRaisesRegex(RuntimeError,'two explicit bundle owners'):
    validate_runtime_support(project,{'objectiveSupportAssets':[shared],'prefabAssets':[shared.lower()]})


if __name__=='__main__':unittest.main()
