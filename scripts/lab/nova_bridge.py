"""Two bounded sequential probes: Unity physical exposure, then original spawned Commando."""
from common import *
import re

RAW='nova-unity-raw'
BODY='body-state-spawn-state-auto-nova-controls'

def insert_axes(before,axes):
    marker='  m_UsePhysicalKeys:'
    if before.count(marker)!=1:raise RuntimeError('InputManager terminal property changed; review before staging')
    index=before.index(marker)
    return before[:index]+axes+before[index:]

def prepare():
    active=WORK/'lab-project/Assets/LabLoadingScene'
    if (active/'Resources/MovementBatchProbe.json').exists() and read(active/'Resources/MovementBatchProbe.json').get('primaryFireConfigAsset'):
        return prepare_spine()
    from scene_runtime import body_start_loadout_prepare
    body_start_loadout_prepare(spawn_states=True,teleport_material=True,nova_input=True,cases=[RAW])
    out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];a=read(out/'attempt.json');stage=Path(a['stage'])
    cfg=read(stage/'Resources/MovementBatchProbe.json');cfg['displayAssets']=[x.lower() for x in read(WORK/'scene-probe-build.json')['prefabAssets'][:6]];write(stage/'Resources/MovementBatchProbe.json',cfg)
    settings=WORK/'lab-project/ProjectSettings/InputManager.asset';before=settings.read_text()
    if 'm_Name: NovaLabAxis' in before:raise RuntimeError('Existing Nova axes must be reviewed/restored first')
    (out/'InputManager-before.asset').write_text(before)
    axes=''
    for i in range(16):
        axes+=f'''  - serializedVersion: 3
    m_Name: NovaLabAxis{i}
    descriptiveName:
    descriptiveNegativeName:
    negativeButton:
    positiveButton:
    altNegativeButton:
    altPositiveButton:
    gravity: 0
    dead: 0
    sensitivity: 1
    snap: 0
    invert: 0
    type: 2
    axis: {i}
    joyNum: 1
'''
    settings.write_text(insert_axes(before,axes))
    request=stage/'Editor/character-motor-order.json';order=read(request);order['novaInputOrder']=-20000;write(request,order)
    a.update({'nova_input_bridge':True,'batch_seconds':{RAW:140,BODY:120}});write(out/'attempt.json',a)
    write(out/'nova-contract.json',{'input_manager_before_sha256':sha(out/'InputManager-before.asset'),'input_manager_after_sha256':sha(settings),'scope':'Nova only; original InputBankTest producer; no movement/state/motor/skill rewrites; no Rewired replacement','prior_art':'Starstorm2 a9a4badd BorgMain consumes inputBank and retains GenericCharacterMain base ProcessJump/FixedUpdate; no Android backend provided','catalog':'Measured JumpBoost/JumpDamageStrike plus GummyCloneIdentifier in original empty inventory; explicit new combined subset, old cases unchanged','mapping':'Measure Unity slot-1 axes/buttons, then push attempt-bound JSON; skills disabled in movement proof','visual':'Recovered transform/renderer-only model display follows original ModelLocator; fixed bind pose, diagnostic floor/camera/aim stance'})

def prepare_spine(director_batch=False,run_clock=False,barrel=False,pickup=False,money=False,client=False,selection=False,client_coin=False,input_barrel=False,chest_drop=False,chest_purchase=False,droplet_load=False,droplet_flight=False,droplet_collision=False,default_pickup=False,chest_ejection=False,integrated_world=False):
    """Continue the accepted active stage; use the measured mapping without repeating its capture."""
    import shutil
    from build import preflight
    preflight();parent=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];a=read(parent/'attempt.json');stage=Path(a['stage'])
    baseline_cfg=read(stage/'Resources/MovementBatchProbe.json')
    if not all(baseline_cfg.get(k) for k in ['bodyAsset','masterAsset','displayAssets']):
        raise RuntimeError('Accepted gameplay configuration missing; restore the archived stage resource, not a build receipt')
    checkpoint=read(WORK/'checkpoints/LAST_KNOWN_GOOD_NOVA_INPUT_BRIDGE.json');mapping=dict(checkpoint['mapping'])
    if checkpoint['input_id']!=read(WORK/'inventory/files.json')['input_id'] or sha(ROOT/mapping['observation'])!=mapping['observation_sha256']:raise RuntimeError('Accepted input/mapping changed')
    for name,h in checkpoint['original_assemblies'].items():
        if sha(stage/'Plugins'/name)!=a.get('transformed_assemblies',{}).get(name,h):raise RuntimeError('Original spine assembly drift')
        if name in a.get('transformed_assemblies',{}):
            original=game()/'Risk of Rain 2_Data/Managed'/name
            if sha(original)!=h:raise RuntimeError('Accepted original input changed')
            shutil.copy2(original,stage/'Plugins'/name)
    out=WORK/'experiments/scene-runtime'/now();out.mkdir(parents=True)
    write(out/'rollback.json',{'physical':read(WORK/'checkpoints/LAST_KNOWN_GOOD_SPINE_PHYSICAL.json') if (WORK/'checkpoints/LAST_KNOWN_GOOD_SPINE_PHYSICAL.json').exists() else checkpoint,'combat':read(WORK/'checkpoints/LAST_KNOWN_GOOD_COMBAT_SCRIPTED.json') if (WORK/'checkpoints/LAST_KNOWN_GOOD_COMBAT_SCRIPTED.json').exists() else None,'primary':read(WORK/'checkpoints/LAST_KNOWN_GOOD_PRIMARY_ACTIVATION.json'),'before':str(parent.relative_to(ROOT)),'build':read(WORK/'config/current-build.json')})
    shutil.copy2(ROOT/checkpoint['evidence']/'original-motor-order.json',out/'original-motor-order.json')
    for name in ['MovementBatchProbe','OfflineApplicationBoundary','IntegratedResultsBoundary','MoonMissionBoundary','IntegratedWorldBoundary','IntegratedStageBoundary','AndroidStageTransport','TeleporterWorldBoundary','PrimaryFireBoundary','CombatSpineBoundary','SilentProjectileBoundary','StageGeometryBoundary','EnemySpineBoundary','EnemyRewardBoundary','AutomaticDirectorBoundary','DirectorActorBoundary','RunClockBoundary','BarrelInteractionBoundary','ActiveClientBoundary','InteractionSelectionBoundary','ClientCoinBoundary','InputBarrelBoundary','ChestDropTableBoundary','ChestPurchaseBoundary','ChestEjectionBoundary','PickupDropletLoadBoundary','PickupDropletFlightBoundary','PickupDropletCollisionBoundary','GenericPickupBoundary','MoneyCostBoundary','ItemPickupBoundary','PlayerDefeatBoundary','BodyCatalogBoundary','SpawnStateBoundary','AutomaticSpawnBoundary','AutomaticModelBoundary','NovaInputBoundary','NovaInputBridge','NovaDiagnosticDisplay','NovaThirdPersonView']:shutil.copy2(ROOT/'tools/unity'/(name+'.cs'),stage/(name+'.cs'))
    for shader in ['StageTerrainPreview','StageSurfacePreview']:shutil.copy2(ROOT/'tools/unity'/(shader+'.shader'),stage/'Resources'/(shader+'.shader'))
    cfg=baseline_cfg;cfg.update(stage_combat_configs(stage,a,out));cfg.update(stage_first_stage_geometry(stage,out,original_name=run_clock,map_zones=integrated_world));cfg.update(stage_enemy_spine(stage,a,out));cfg.update({'attempt':out.name,'combatSpine':True,'launchPlayableSlice':True,'originalRunClock':run_clock})
    if run_clock:cfg.update(stage_run_scene_metadata(stage,out))
    if integrated_world:
        from integrated_objective import stage_objective
        cfg.update(stage_objective(stage,a,out))
        cfg['integratedStages']=[stage_first_stage_geometry(stage,out,original_name=True,scene_name=name,map_zones=name!='moon2') for name in ['foggyswamp','frozenwall','dampcavesimple','skymeadow','moon2']]
        from integrated_moon import stage_moon
        moon=stage_moon(stage,a,out,cfg['integratedStages'][-1])
        cfg['objectiveConfigAssets']=list(dict.fromkeys(cfg['objectiveConfigAssets']+moon['configs']))
        cfg['objectiveActors']+=moon['actors']
        cfg['runSceneDefAssets']=list(dict.fromkeys(cfg['runSceneDefAssets']+[moon['sceneDef']]))
        cfg['objectiveSupportAssets'].append(moon['pillar'])
        cfg['objectiveSupportKeys'].append(moon['pillarKey'])
        cfg['objectiveSupportPaths'].append('Prefabs/PositionIndicators/PillarChargingPositionIndicator')
        cfg['moonCatalog']=moon['catalog']
        for support in moon['supports']:
            cfg['objectiveSupportAssets'].append(support['asset'])
            cfg['objectiveSupportKeys'].append(support['key'])
            cfg['objectiveSupportPaths'].append(support['path'])
        from integrated_results import stage_results
        cfg.update(stage_results(stage,out,a))
        cfg['moonMission']=True
        cfg['integratedTransitionTarget']=5
        cfg['integratedRuntimeSeconds']=3300
    cfg['integratedWorld']=integrated_world;cfg['barrelInteraction']=barrel;cfg['originalItemPickup']=pickup;cfg['originalMoneyCost']=money;cfg['originalActiveClient']=client;cfg['originalInteractionSelection']=selection;cfg['originalClientCoin']=client_coin;cfg['originalInputBarrel']=input_barrel;cfg['originalChestDropTable']=chest_drop;cfg['originalChestPurchase']=chest_purchase;cfg['originalPickupDropletLoad']=droplet_load;cfg['originalPickupDropletFlight']=droplet_flight;cfg['originalPickupDropletCollision']=droplet_collision;cfg['originalDefaultPickup']=default_pickup;cfg['originalChestEjection']=chest_ejection
    if barrel:
        if not run_clock or not director_batch:raise RuntimeError('Barrel probe requires accepted clock and three-actor context')
        cfg.update(stage_barrel(stage,out,pickup=pickup,money=money,selection=selection,drop_table=chest_drop,purchase=chest_purchase,droplet_load=droplet_load,droplet_flight=droplet_flight,previous=a,integrated_world=integrated_world))
    if client_coin:
        if not selection or not client:raise RuntimeError('Client coin probe requires accepted original selection/active-client context')
        write(out/'client-coin-contract.json',{'rollback':read(WORK/'checkpoints/LAST_KNOWN_GOOD_INTERACTION_SELECTION.json'),'count':683,'source_tiers':[500,150,25,5,1],'expected_bursts':[1,1,1,1,3],'source_duration':3,'scope':'Original message52/client factory/CoinBehavior/timer pool return with cosmetic diagnostic count; no funds grant, interaction/reward linkage, physical input/audio/graphics parity. Original pooling/randomness retained; only skipped original medium-budget declared default200 initialized through original setter and restored, no full Console claim.','prior_art':'Pinned R2API.ContentManagement f539511e R2APISerializableContentPack registers genuine prefabs through original EffectDef. Exact EffectManager/EffectData/CoinBehavior/DestroyOnTimer/EffectPool and immutable prefab determine network/lifetime contracts; no implementation copied.'})
    if input_barrel:
        if not client_coin or not selection or not client:raise RuntimeError('Input barrel requires accepted coin/selection/client context')
        write(out/'input-barrel-contract.json',{'rollback':read(WORK/'checkpoints/LAST_KNOWN_GOOD_CLIENT_COIN.json'),'scope':'Original automatic InteractionDriver input/selection/server cash barrel dispatch, timed gold/XP and genuine client message52/55 decoding; source count coin lifetime/pool return. Diagnostic input/manual placement; original optional XP cosmetics disabled through original setting and restored, no native audio/physical interaction/normal placement/purchase/drop/profile/full startup claim.','xp_option':'Record prior0/declared1/active0/restored0. Genuine original handler decodes before original option guard; no fake empty handler or native XP orb sound.','prior_art':'Pinned Starstorm2 a9a4badd BorgMain preserves original inputBank/base state boundary; R2API.CommandHelper f539511e separates Console readiness/default application; R2API.ContentManagement original EffectDef registration. Exact current InteractionDriver/Interactor/InputBankTest/BarrelInteraction/ExperienceManager/SettingsConVars/CoinBehavior determines measured Android candidate. No implementation copied.'})
    recipe=read(WORK/'scene-probe-build.json')
    if chest_ejection:
        if not default_pickup or not droplet_collision:raise RuntimeError('Chest ejection requires accepted original generic/droplet source leases')
        write(out/'chest-ejection-contract.json',{'rollback':read(WORK/'checkpoints/LAST_KNOWN_GOOD_DEFAULT_PICKUP.json'),'scope':'Original source Animator/AnimationEvents/effects/ItemDrop/native collision/default pickup/direct display. Diagnostic source chest funding/placement and original character input withdrawal; no manually dispatched drop/factory/physics/effect, grant/normal progression/full startup acceptance.','expected':'Original rolled base identity/no override/chest linkage, one pickup, three pooled effects/natural returns, delayed availability, owned cleanup and sixty-second original client hold.'})
    if default_pickup:
        if not droplet_collision:raise RuntimeError('Default factory requires accepted source collision context')
        query=read(WORK/'config/default-pickup-catalog.json')
        if query['input_id']!=read(WORK/'inventory/files.json')['input_id']:raise RuntimeError('Default pickup catalog input changed')
        cfg['genericPickupKey']=query['key'];recipe['genericPickup']=cfg['pickupAsset'];recipe['prefabAssets']=[x for x in recipe['prefabAssets'] if x.lower()!=cfg['pickupAsset'].lower()]
        write(out/'default-pickup-contract.json',dict(query,rollback=read(WORK/'checkpoints/LAST_KNOWN_GOOD_PICKUP_DROPLET_COLLISION.json'),scope='Original generic sync/async/genuine Init and no-override default factory/active PickupDisplay/direct Syringe model/natural spin/delay, diagnostic material/view layer only. No display suppression/model loader/manual physics/grant/chest ejection/audio/full startup acceptance.',prior_art='Pinned R2API.Addressables f539511e handle ownership and DebugToolkit d1e2f0aa original factory; exact current GenericPickupController/PickupDisplay/ItemDef/AssetOrDirectReference and typed direct-model source govern candidate. No implementation copied.'))
    else:recipe.pop('genericPickup',None)
    write(WORK/'scene-probe-build.json',recipe)
    if droplet_collision:
        if not droplet_flight:raise RuntimeError('Native collision requires accepted source/free-flight context')
        write(out/'pickup-droplet-collision-contract.json',{'rollback':read(WORK/'checkpoints/LAST_KNOWN_GOOD_PICKUP_DROPLET_FLIGHT.json'),'scope':'Original source factory/native recovered-terrain collision/original generic factory/Start/delay with public diagnostic prefabOverride using S146 owned original template/audio/display omissions. No default generic Init/chest Animator/ejection/grant/pickup model/native audio/physical interaction/full startup acceptance.','assertions':'Measured clear terrain and original collision matrix/physics; read-only native callback witness, original collision position and one pickup/network mappings, natural droplet destruction, original0.5-second delay/permission, conserved funds/items/XP and owned map/template/catalog/lease/bundle cleanup.','prior_art':'Pinned DebugToolkit d1e2f0aa Items.CCCreatePickup public original CreatePickupInfo/factory; R2API.Addressables f539511e handle ownership. Exact current source PickupDropletController/GenericPickupController/Run/source terrain determine this collision boundary; no implementation copied.'})
    if droplet_flight:
        if not droplet_load:raise RuntimeError('Flight requires accepted original source loader')
        write(out/'pickup-droplet-flight-contract.json',{'rollback':read(WORK/'checkpoints/LAST_KNOWN_GOOD_PICKUP_DROPLET_LOAD.json'),'scope':'Original public source factory and natural automatic callbacks/native Rigidbody free-flight. Diagnostic high-altitude placement/velocity and temporary original base pickup catalog; original disabled Command preserved, existing empty tier catalog means no droplet display. No collision/pickup creation/chest Animator/ejection/grant/visual/audio/full startup acceptance.','assertions':'Exact original info/UniquePickup/network mappings/source caches/authority and0.5-fixed-second motion with actual ticks/source gravity, drag, constant force. Observe original network updates; no collision/new pickup/conservation, owned server/client object removal/catalog/lease/bundle restore.','prior_art':'Pinned DebugToolkit d1e2f0aa Items.CCCreatePickup uses original CreatePickupInfo/public droplet factory; R2API.Addressables f539511e original handle ownership. Current original PickupDropletController/ProjectileNetworkTransform/CommandArtifactManager/ItemDef and source physics govern this diagnostic flight; no implementation copied.'})
    if droplet_load:
        if not chest_purchase:raise RuntimeError('Droplet load requires accepted chest purchase context')
        query=read(WORK/'config/pickup-droplet-catalog.json')
        if query['input_id']!=read(WORK/'inventory/files.json')['input_id'] or query['catalog_sha256']!=read(WORK/'config/enemy-reward-catalog.json')['catalog_sha256']:raise RuntimeError('Droplet catalog input changed')
        cfg['pickupDropletKey']=query['key'];write(out/'pickup-droplet-contract.json',dict(query,rollback=read(WORK/'checkpoints/LAST_KNOWN_GOOD_CHEST_PURCHASE.json'),scope='Original sync/async source prefab plus actual single-load PickupDropletController.Init callback and owned reference/locator/bundle cleanup. No instantiation/factory/animation/physics/grant/native audio/full startup acceptance.',prior_art='Pinned R2API.Addressables f539511e original handle/release semantics; DebugToolkit d1e2f0aa Items.CCCreatePickup calls original droplet factory. Original current Init/Start/CreatePickup and measured source/catalog govern this distinct loader boundary; no implementation copied.'))
    if chest_purchase:
        if not chest_drop or not input_barrel:raise RuntimeError('Chest purchase requires accepted loot/input contracts')
        write(out/'chest-purchase-contract.json',{'rollback':read(WORK/'checkpoints/LAST_KNOWN_GOOD_CHEST_DROP_TABLE.json'),'scope':'Original source Chest1 natural lifecycle/roll, serialized callbacks, public interaction input, original payment25 and Opening/Opened. Diagnostic funding8+17/manual source placement/two-item Run domain. Animator disabled, source SfxLocator omitted only on owned clone; no ejection/physics/grant/visual opening/native audio/normal placement/profile/startup acceptance.','prerequisites':'Original FreeUnlocks buff zero, LowerPricedChests/Consumed locked/ungranted, original Delusion disabled and its natural Start disables secondary picker/prompt. Source dropTransform null is original Awake root fallback, not missing content. Original source table regenerates on explicit base lists and restores empty cache.','assertions':'Persistent targets/methods, source cost/policy/roll, unaffordable input no payment, funded original detailed/global purchase once, wallet25 to0, source FSM Opening toOpened, repeat rejection, actual secondary unavailable and cleanup.','prior_art':'Pinned R2API.Director f539511e InteractableSpawnCardClone separates placement/eligibility/stage caps; DebugToolkit d1e2f0aa Items.CollectItemTiers separates Run domains/table. Exact current PurchaseInteraction/ChestBehavior/DelusionChestController/Picker/InputDriver and prefab govern callbacks and zero-count contracts; no original/community implementation copied.'})
    if chest_drop:
        if not input_barrel:raise RuntimeError('Chest table requires accepted input-barrel context')
        write(out/'chest-drop-table-contract.json',{'rollback':read(WORK/'checkpoints/LAST_KNOWN_GOOD_INPUT_BARREL.json'),'scope':'Original recovered dtChest1/BasicPickupDropTable RNG/UniquePickup generation with unchanged source weights/replacement policy. Explicit base tier1 Syringe/tier2 ChainLightning diagnostic items in diagnostic Run lists; no tier3/other domain, full Run availability/chest/purchase/drop physics/grant/profile/progression claim. Original RandomlyLunar definition cataloged before inventories but locked/ungranted; no replacement feature success.','seeds':[123456789,987654321,42],'draws':64,'assertions':'Equal seed reproduces exact64 draws, alternate differs, both allowed choices occur; distinct2, desired5 with loop5/without loop2, exact catalog/table/list restoration and conserved inventory/money/XP.','prior_art':'Pinned DebugToolkit d1e2f0aa Items.InitDroptableData/CollectItemTiers separates original BasicPickupDropTable from Run available tier lists. Use recovered source table rather than a custom weighted table. Exact current BasicPickupDropTable/PickupDropTable/RandomlyLunarUtils/Xoroshiro/UniquePickup and immutable dtChest1 determine contract. No implementation copied.'})
    write(stage/'Resources/MovementBatchProbe.json',cfg)
    cfg['directorSpawnLimit']=3 if director_batch else 1;write(stage/'Resources/MovementBatchProbe.json',cfg)
    if director_batch:
        accepted=read(WORK/'checkpoints/LAST_KNOWN_GOOD_AUTOMATIC_DIRECTOR_NAVIGATION.json')
        write(out/'director-batch-contract.json',{'rollback':accepted,'limit':3,'scope':'Original enabled director until three natural spawns; individually observe each original master/body/AI/route/combat/death/reward/cleanup. No manual credits/spawn/reward or pose writes. Diagnostic input only; no full deck/elites/stage progression.','prior_art':'Pinned R2API.Director f539511e separates Unity enabled scheduling from disabled-director ticks; exact original OnSpawnedServer and MasterSummon global events identify each actor. Original source cost accounting and TeamManager/ExperienceManager determine aggregate rewards; no implementation copied.'})
    if run_clock:write(out/'run-clock-contract.json',{'rollback':read(WORK/'checkpoints/LAST_KNOWN_GOOD_MULTI_ACTOR_COMBAT.json'),'scope':'Original source SceneDef and SceneCatalog initialization on the same recovered geometry using its original scene name; original Run Update/FixedUpdate scheduled by the lab while Run/GameApplication remain inactive. Original stopwatch/time/difficulty, no manual clock or fake stage progression/entitlement.','prior_art':'Pinned R2API.Director f539511e InitStageEnumToSceneDefs waits for original SceneCatalog.Init before using stage definitions. Exact original Run.FixedUpdate requires SceneCatalog.mostRecentSceneDef and live-player count; original GenericPickupController wait uses Run.FixedTimeStamp.'})
    spine='body-state-spawn-state-auto-nova-spine'
    a.update({'attempt':out.name,'playable_spine':True,'enemy_spine':True,'nova_input_bridge':True,'parent':str(parent.relative_to(ROOT)),'batch_ids':[spine+'-bringup'],'batch_seconds':{spine+'-bringup':150,spine:180},'batch_stop_when_complete':[spine+'-bringup']});write(out/'attempt.json',a)
    if client:
        a['batch_seconds'][spine+'-bringup']=180
        write(out/'active-client-contract.json',{'rollback':read(WORK/'checkpoints/LAST_KNOWN_GOOD_MONEY_COST.json'),'scope':'Actual local client readiness/active original body-master registry, original raw client authority callbacks/60-second neutral simulation and owned client teardown. No NetworkUser/LocalUser/platform session/entitlement grant or InteractionDriver/remote-peer acceptance. ClientScene shared transport cleanup only after owned server shutdown.','prior_art':'Pinned DebugToolkit d1e2f0aa Code/NetworkManager/Util observes actual network objects/master relationships. J102-J106 original state catalog/cache/tracker-storage/readiness failures and fixes reused; current exact original HLAPI/CharacterBody/SkillLocator/NetworkStateMachine/entitlement tracker APIs govern active-actor proof. No implementation copied.'})
    a['director_batch']=director_batch
    if integrated_world:
        a['integrated_world']=True;a['batch_seconds'][spine+'-bringup']=240
        mapping.update({'interact':1,'enableInteraction':True})
        write(out/'whole-game-contract.json',{'scope':'Persistent composed stage/player/third-person camera/skills/teleporter/boss/director/rewards/barrels/chests/droplets/pickups/local-client/authority/HUD. Source unlocked four-item loot domain, owned placement/materials and silent pickup message adapter. No stock startup/menu/profile/stage transition/victory claim.', 'prior_art':'Pinned R2API.Director f539511e original SceneCatalog/director activity, R2API.ContentManagement EffectDef registration and DebugToolkit d1e2f0aa Run drop lists/original pickup factories; exact current original APIs and prior Nova evidence govern integration. No source implementations copied.','rollback':read(WORK/'checkpoints/LAST_KNOWN_GOOD_INTEGRATED_WORLD.json'),'loot_items':['Syringe','CritGlasses','HealWhileSafe','ChainLightning'],'interaction_binding':'Measured Nova Unity button1 = physical B from accepted full capture; original inputBank.interact boundary.'})
    if integrated_world:
        from integrated_objective import transform_optional_presentation,sanitize_optional_content
        a['teleporter_loop']=True;a['batch_seconds'][spine+'-bringup']=3540
        cfg.update(sanitize_optional_content(stage,out))
        transform_optional_presentation(stage,out,a)
        write(stage/'Resources/MovementBatchProbe.json',cfg)
    write(out/'attempt.json',a)
    mapping['accepted_mapping_attempt']=mapping['attempt'];mapping['attempt']=out.name;write(out/'nova-input-mapping.json',mapping)
    write(WORK/'experiments/scene-runtime/current.json',{'path':str(out.relative_to(ROOT))});print(json.dumps({'attempt':str(out.relative_to(ROOT)),'spine':True}))

def stage_combat_configs(stage,previous,out):
    """Existing YAML closure traversal for the three default Commando state configurations."""
    import shutil
    export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0];index={};existing={}
    for base,target in [(export/'Assets',index),(stage,existing)]:
        for meta in base.rglob('*.meta'):
            match=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(errors='replace'),re.M)
            if match:target[match[1]]=Path(str(meta)[:-5])
    skills=export/'Assets/RoR2/Base/Characters/Commando/Skills'
    roots={'secondaryConfigAsset':skills/'EntityStates.Commando.CommandoWeapon.FireFMJ.asset','utilityConfigAsset':skills/'EntityStates.Commando.DodgeState.asset','specialConfigAsset':export/'Assets/RoR2/Junk/Characters/CommandoPerformanceTest/EntityStates.Commando.CommandoWeapon.FireBarrage.asset'}
    pending=list(roots.values());seen=set();paths={};rows=[];remaps={r['from']:r['to'] for r in previous.get('ui_remaps',[])}
    while pending:
        src=pending.pop()
        if src in seen:continue
        seen.add(src);meta=Path(str(src)+'.meta');guid=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(),re.M)[1]
        if src.suffix=='.dll':
            if src.name=='UnityEngine.UI.dll' and remaps:continue
            if guid not in existing:raise RuntimeError('Unprovided combat assembly '+src.name)
            continue
        dst=existing.get(guid,stage/'CombatClosure'/src.relative_to(export/'Assets'))
        if guid not in existing:
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);shutil.copy2(meta,Path(str(dst)+'.meta'))
        rows.append({'source':str(src.relative_to(export)),'source_sha256':sha(src),'staged':str(dst.relative_to(WORK/'lab-project')),'reused':guid in existing})
        for key,value in roots.items():
            if src==value:paths[key]=str(dst.relative_to(WORK/'lab-project'))
        if src.read_bytes()[:5]==b'%YAML':
            if guid not in existing:
                text=dst.read_text()
                for old,new in remaps.items():text=text.replace(old,new)
                dst.write_text(text)
            for dep in set(re.findall(r'guid: ([a-f0-9]{32})',src.read_text())):
                if dep.startswith('0000000000000000'):continue
                if dep not in index:raise RuntimeError('Unresolved combat GUID')
                pending.append(index[dep])
    recipe=read(WORK/'scene-probe-build.json');recipe['prefabAssets']=list(dict.fromkeys(recipe['prefabAssets']+list(paths.values())));write(WORK/'scene-probe-build.json',recipe)
    write(out/'combat-contract.json',{'scope':'Integrated default FMJ/roll/barrage and original BulletAttack/HealthComponent target; explicit silent effects-excluded owned copies','prior_art':'Pinned Starstorm2 a9a4badd Deadeye uses authority-gated original BulletAttack and separate visual effects; BorgMain retains original inputBank/GenericCharacterMain behavior. No community code copied.','special_config':'Only exported configuration for exact FireBarrage targetType; preserve its original parameters despite recovered Junk directory.','closure':rows})
    return {key:value.lower() for key,value in paths.items()}


def stage_first_stage_geometry(stage,out,original_name=False,scene_name="golemplains",map_zones=False):
    """Recover source geometry; integrated runs additionally retain exact MapZone callbacks."""
    import shutil
    from scene_closure import REFERENCE
    export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    source=export/('Assets/RoR2/Base/Scenes/'+scene_name+'/'+scene_name+'.unity')
    text=source.read_text();header=text[:text.index('--- !u!')];blocks=re.split(r'(?=^--- !u!)',text,flags=re.M)[1:]
    # Preserve geometry/LOD and selected source MapZone callbacks; omit unrelated native/presentation data.
    keep={1,4,23,33,64,65,135,136,137,205,224};kept=[];removed=set();root_objects=set();counts={};preview_ids=[]
    # Measured original MonoScript identity: only the source escape-pod preview disable callback.
    preview_script="m_Script: {fileID: 866789372, guid: 951ce57ad999ac1f040a4dceb5f8b763, type: 3}"
    map_script="m_Script: {fileID: -376374237, guid: 951ce57ad999ac1f040a4dceb5f8b763, type: 3}"
    map_blocks=[b for b in blocks if b.startswith('--- !u!114 ') and map_script in b] if map_zones else []
    expected_zones={'golemplains':1,'foggyswamp':5,'frozenwall':2,'dampcavesimple':4,'skymeadow':2}
    if map_zones and len(map_blocks)!=expected_zones.get(scene_name):raise RuntimeError('Original stage MapZone contract changed; review source')
    map_owners={re.search(r'm_GameObject: \{fileID: (-?\d+)\}',b)[1] for b in map_blocks}
    by_id={re.match(r'--- !u!\d+ &(-?\d+)',b)[1]:b for b in blocks}
    map_active=[]
    def source_name(block):
        value=re.search(r'^  m_Name: (.*)$',block,re.M)[1]
        if value.startswith("'") and value.endswith("'"):return value[1:-1].replace("''", "'")
        return json.loads(value) if value.startswith('"') else value
    for owner in map_owners:
        if '  m_IsActive: 1' in by_id[owner]:map_active.append(source_name(by_id[owner]))
        transform=next(b for b in blocks if b.startswith('--- !u!4 ') and re.search(r'm_GameObject: \{fileID: (-?\d+)\}',b)[1]==owner)
        if '  m_Children: []' not in transform:raise RuntimeError('MapZone owner has unreviewed children')
    map_active.sort()
    map_network_script="m_Script: {fileID: 372142912, guid: d382a022563c7517aadbc92ca1060016"
    identities={tuple(row.split('|')[:2]):row.split('|')[2] for row in (WORK/'moon-script-identities.txt').read_text().splitlines()} if map_owners else {}
    map_team_id=next((identity for identity,name in identities.items() if name=='RoR2.TeamFilter'),None)
    map_extra=[]
    map_network_ids=[re.match(r'--- !u!114 &(-?\d+)',b)[1] for b in blocks if b.startswith('--- !u!114 ') and map_network_script in b and re.search(r'm_GameObject: \{fileID: (-?\d+)\}',b)[1] in map_owners]
    if map_network_ids and map_team_id is None:raise RuntimeError('Original MapZone TeamFilter identity missing')
    if map_network_ids and (scene_name!='skymeadow' or len(map_network_ids)!=2):raise RuntimeError('Original MapZone network scope changed')
    map_ids=[re.match(r'--- !u!114 &(-?\d+)',b)[1] for b in map_blocks];deferred_colliders=[]
    for block in blocks:
        match=re.match(r'--- !u!(\d+) &(-?\d+)',block);kind=int(match[1]);file_id=match[2]
        preview=kind==114 and preview_script in block
        if preview:preview_ids.append(file_id)
        owner=re.search(r'm_GameObject: \{fileID: (-?\d+)\}',block)
        script=re.search(r'm_Script: \{fileID: (-?\d+), guid: ([a-f0-9]+)',block)
        map_context=kind==114 and owner and owner[1] in map_owners and script and (map_network_script in block or script.groups()==map_team_id)
        if map_context:map_extra.append(file_id)
        map_zone=kind==114 and map_zones and map_script in block
        if kind not in keep and not preview and not map_zone and not map_context:removed.add(file_id);counts[str(kind)]=counts.get(str(kind),0)+1;continue
        if kind in {4,224} and re.search(r'm_Father: \{fileID: 0\}',block):root_objects.add(re.search(r'm_GameObject: \{fileID: (-?\d+)\}',block)[1])
        if kind in {64,65,135,136} and re.search(r'm_GameObject: \{fileID: (-?\d+)\}',block)[1] in map_owners:
            if '  m_IsTrigger: 1' not in block or '  m_Enabled: 1' not in block:raise RuntimeError('Original MapZone collider contract differs')
            deferred_colliders.append(file_id)
        kept.append((kind,file_id,block))
    if len(deferred_colliders)!=len(map_ids):raise RuntimeError('Original MapZone collider count differs')
    expected_previews={'golemplains':23,'foggyswamp':0,'frozenwall':23,'dampcavesimple':1,'skymeadow':12,'moon2':0}
    if scene_name not in expected_previews or len(preview_ids)!=expected_previews[scene_name]:raise RuntimeError("Measured original escape-pod preview callback set changed; review source")
    updated=[]
    for kind,file_id,block in kept:
        if kind==1:
            if file_id in map_owners:block=block.replace('  m_IsActive: 1','  m_IsActive: 0',1)
            block=re.sub(r'^  - component: \{fileID: (-?\d+)\}\n',lambda m:'' if m[1] in removed else m[0],block,flags=re.M)
        updated.append(block)
    geometry=header+''.join(updated);dest=stage/'StageGeometry'/(scene_name+'.unity' if original_name else scene_name+'-spine.unity');dest.parent.mkdir(parents=True,exist_ok=True)
    other=dest.with_name(scene_name+'-spine.unity' if original_name else scene_name+'.unity')
    if other.exists():
        if Path(str(other)+'.meta').read_bytes()!=Path(str(source)+'.meta').read_bytes():raise RuntimeError('Refuse to remove an unowned alternate stage scene')
        other.unlink();Path(str(other)+'.meta').unlink()
    dest.write_text(geometry);shutil.copy2(Path(str(source)+'.meta'),Path(str(dest)+'.meta'))
    index={};existing={}
    for base,target in [(export/'Assets',index),(stage,existing)]:
        for meta in base.rglob('*.meta'):
            m=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(errors='replace'),re.M)
            if m:target[m[1]]=Path(str(meta)[:-5])
    pending=[guid for _,guid,_ in REFERENCE.findall(geometry) if guid and not guid.startswith('0000000000000000')];seen=set();rows=[]
    while pending:
        guid=pending.pop()
        if guid in seen:continue
        seen.add(guid)
        if guid not in index:raise RuntimeError('Unresolved static stage dependency '+guid)
        src=index[guid]
        if src.suffix=='.dll':
            if src.name=='RoR2.dll' and guid in existing and existing[guid]==stage/'Plugins/RoR2.dll':continue
            if src.name=='com.unity.multiplayer-hlapi.Runtime.dll' and guid in existing and existing[guid]==stage/'Plugins'/src.name and sha(existing[guid])==sha(game()/'Risk of Rain 2_Data/Managed'/src.name):continue
            raise RuntimeError('Unexpected managed dependency in static geometry '+src.name)
        dst=existing.get(guid,stage/'StageGeometry/Assets'/src.relative_to(export/'Assets'))
        if guid not in existing:
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);shutil.copy2(Path(str(src)+'.meta'),Path(str(dst)+'.meta'))
        with src.open('rb') as stream:prefix=stream.read(5)
        if prefix==b'%YAML':pending.extend(g for _,g,_ in REFERENCE.findall(src.read_text()) if g and not g.startswith('0000000000000000'))
        rows.append({'source':str(src.relative_to(export)),'source_sha256':sha(src),'bytes':src.stat().st_size,'staged':str(dst.relative_to(WORK/'lab-project')),'reused':guid in existing})
    recipe=read(WORK/'scene-probe-build.json')
    if scene_name=='golemplains':recipe['stageScene']=str(dest.relative_to(WORK/'lab-project'))
    else:
        recipe['nextStageScenes']=list(dict.fromkeys(recipe.get('nextStageScenes',[])+[str(dest.relative_to(WORK/'lab-project'))]))
        recipe.pop('nextStageScene',None)
    write(WORK/'scene-probe-build.json',recipe)
    write(out/('stage-geometry-contract.json' if scene_name=='golemplains' else scene_name+'-geometry-contract.json'),{'source':str(source.relative_to(export)),'source_sha256':sha(source),'generated_sha256':sha(dest),'removed_classes':counts,'kept_classes':sorted(keep|{114}),'retained_components':{'DisableOnStart':preview_ids,'MapZone':map_ids,'MapZoneContext':map_extra},'deferred_map_objects':sorted(map_owners),'source_active_map_names':map_active,'map_network_objects':map_network_ids,'roots':len(root_objects),'source_active_flags_preserved':not map_owners,'closure':rows,'bytes':sum(x['bytes'] for x in rows),'scope':'Recovered geometry/LOD/collision and source preview callbacks; optional exact original MapZone volumes activate after owned runtime context/entry and pause during continuous-body transport. No full stock scene/director/lighting parity. Runtime materials remain diagnostic.','prior_art':'Pinned Starstorm2 a9a4badd SlateMines uses SceneAssetCollection/SceneDef; pinned R2API.Director hooks ClassicStageInfo.Start/SceneCatalog.Init and documents1.4.0 DCCS timing. Those lifecycle contracts are deliberately not claimed by static geometry. Existing closure algorithm reused; no community code copied.'})
    if scene_name=='golemplains':return {'stageGeometry':True,'stageMapZoneCount':len(map_ids),'stageMapZoneActiveNames':map_active}
    graphs={}
    for kind in ['ground','air']:
        guid=re.search(r'^  '+kind+r'NodesAsset: \{fileID: -?\d+, guid: ([a-f0-9]{32})',text,re.M)[1]
        src=index[guid];dst=existing.get(guid,stage/'StageGeometry/Assets'/src.relative_to(export/'Assets'))
        if not dst.exists():
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);shutil.copy2(Path(str(src)+'.meta'),Path(str(dst)+'.meta'))
        graphs[kind+'Graph']=str(dst.relative_to(WORK/'lab-project')).lower()
    recipe=read(WORK/'scene-probe-build.json');recipe['prefabAssets']=list(dict.fromkeys(recipe['prefabAssets']+list(graphs.values())));write(WORK/'scene-probe-build.json',recipe)
    write(out/(scene_name+'-navigation-contract.json'),dict(source_scene_sha256=sha(source),graphs={kind:dict(path=path,sha256=sha(next(p for p in stage.rglob('*.asset') if str(p.relative_to(WORK/'lab-project')).lower()==path))) for kind,path in graphs.items()},scope='Actual source SceneInfo ground/air graph references; Android transport keeps original Run accounting and local authority, continuous-body adapter declared separately.'))
    source_blocks={fid:(kind,block) for kind,fid,block in kept}
    preview_names=[]
    for fid in preview_ids:
        go_id=re.search(r'm_GameObject: \{fileID: (-?\d+)\}',source_blocks[fid][1])[1]
        preview_names.append(re.search(r'^  m_Name: (.*)$',source_blocks[go_id][1],re.M)[1])
    expected_names=['HELPER LIGHT'] if scene_name=='dampcavesimple' else ['EscapePodMesh']*len(preview_ids)
    if sorted(preview_names)!=sorted(expected_names):raise RuntimeError('Original preview object names changed; review source')
    def object_path(go_id):
        go=source_blocks[go_id][1];name=re.search(r'^  m_Name: (.*)$',go,re.M)[1]
        if name.startswith("'") and name.endswith("'"):name=name[1:-1].replace("''", "'")
        elif name.startswith('"'):name=json.loads(name)
        tids=[fid for fid in re.findall(r'component: \{fileID: (-?\d+)\}',go) if fid in source_blocks and source_blocks[fid][0] in {4,224}]
        if len(tids)!=1:raise RuntimeError('Source empty-mesh transform identity ambiguous')
        parent=re.search(r'm_Father: \{fileID: (-?\d+)\}',source_blocks[tids[0]][1])[1]
        if parent=='0':return name
        parent_go=re.search(r'm_GameObject: \{fileID: (-?\d+)\}',source_blocks[parent][1])[1]
        return object_path(parent_go)+'/'+name
    empty=[]
    for kind,fid,block in kept:
        if kind in {33,64,137} and re.search(r'^  m_Mesh: \{fileID: 0\}$',block,re.M):
            go_id=re.search(r'm_GameObject: \{fileID: (-?\d+)\}',block)[1]
            empty.append(dict(component=fid,kind=kind,path=object_path(go_id)))
    write(out/(scene_name+'-source-empty-meshes.json'),dict(source_scene_sha256=sha(source),components=empty,scope='Exact source-null fields and hierarchy identities; no blanket missing-reference allowance or mesh replacement. Source tree siblings retain populated meshes.'))
    return dict(name=scene_name,bundle=scene_name+'-spine-lab',scene=str(dest.relative_to(WORK/'lab-project')).lower(),previewCallbacks=len(preview_ids),previewNames=preview_names,mapZoneCount=len(map_ids),mapZoneActiveNames=map_active,mapZoneNetworkObjects=len(map_network_ids),emptyMeshPaths=[x['path'] for x in empty if x['kind'] in {33,137}],emptyColliderPaths=[x['path'] for x in empty if x['kind']==64],**graphs)


def stage_enemy_spine(stage,previous,out):
    """Exact Beetle prefab/config/visual and Titanic Plains navigation closure for original AI."""
    import shutil
    from scene_closure import REFERENCE
    export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0];index={};existing={}
    for base,target in [(export/'Assets',index),(stage,existing)]:
        for meta in base.rglob('*.meta'):
            m=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(errors='replace'),re.M)
            if m:target[m[1]]=Path(str(meta)[:-5])
    beetle=export/'Assets/RoR2/Base/Characters/BeetleGroup/Beetle';body=beetle/'BeetleBody.prefab';scene=(export/'Assets/RoR2/Base/Scenes/golemplains/golemplains.unity').read_text()
    catalog=read(WORK/'config/enemy-catalog.json')
    if catalog['input_id']!=read(WORK/'inventory/files.json')['input_id'] or catalog['catalog_sha256']!=sha(export/'Assets/StreamingAssets/aa/catalog.json'):
        raise RuntimeError('Enemy catalog input changed; repeat original catalog query')
    runtime={}
    for row in catalog['locations']:
        src=export/row['internalId']
        if src.exists():runtime[row['key']]=src
    def addressed(field,kind):
        block=re.search(field+r':\n((?:    .*\n){3})',body.read_text())[1]
        key=re.search(r'm_AssetGUID: ([a-f0-9]{32})',block)[1]
        locations=[x for x in catalog['locations'] if x['key']==key and x['type']==kind]
        if len(locations)!=1:raise RuntimeError('Unexpected enemy runtime address '+field)
        src=export/locations[0]['internalId']
        if kind=='UnityEngine.Avatar':
            sub=re.search(r'm_SubObjectName: (.*)',block)[1]
            candidates=[p for p in src.parent.glob('*.asset') if re.search(r'^--- !u!90 ',p.read_text(errors='replace'),re.M) and re.search(r'^  m_Name: '+re.escape(sub)+r'$',p.read_text(errors='replace'),re.M)]
            if len(candidates)!=1:raise RuntimeError('Unresolved enemy avatar subobject '+sub)
            src=candidates[0];runtime[key]=src
        if not src.exists():raise RuntimeError('Unresolved recovered enemy address '+field)
        return src
    roots={'enemyBodyAsset':body,'enemyMasterAsset':beetle/'BeetleMaster.prefab','enemySpawnConfigAsset':beetle/'EntityStates.BeetleMonster.SpawnState.asset','enemyAttackConfigAsset':beetle/'Skills/EntityStates.BeetleMonster.HeadbuttState.asset','enemySleepConfigAsset':beetle/'Skills/EntityStates.SleepState.asset'}
    for key,field in [('enemyGroundGraphAsset','groundNodesAsset'),('enemyAirGraphAsset','airNodesAsset')]:
        roots[key]=index[re.search(field+r': \{fileID: -?\d+, guid: ([a-f0-9]{32})',scene)[1]]
    roots['enemyControllerAsset']=addressed('_animatorControllerAddress','UnityEngine.RuntimeAnimatorController')
    roots['enemyAvatarAsset']=addressed('_avatarAddress','UnityEngine.Avatar')
    params=(beetle/'skinBeetleDefault_params.asset').read_text();material_key=re.search(r'defaultMaterialAddress:\n      m_AssetGUID: ([a-f0-9]{32})',params)[1];roots['enemyMaterialAsset']=runtime[material_key]
    death_items=['RoR2/Base/Items/ExtraLife/ExtraLife.asset','RoR2/Base/Items/ExtraLife/ExtraLifeConsumed/ExtraLifeConsumed.asset','RoR2/DLC1/Items/ExtraLifeVoid/ExtraLifeVoid.asset','RoR2/DLC1/Items/ExtraLifeVoid/ExtraLifeVoidConsumed.asset']
    for i,path in enumerate(death_items):roots['enemyDeathItem'+str(i)]=export/'Assets'/path
    for i,name in enumerate(['HealAndRevive','HealAndReviveConsumed']):roots['enemyDeathEquipment'+str(i)]=export/'Assets/RoR2/DLC2/Equipment/HealAndRevive'/(name+'.asset')
    roots['enemyDeathBuffAsset']=export/'Assets/RoR2/DLC2/Interactables/Shrines/ShrineColossusAccess/bdExtraLifeBuff.asset'
    roots['enemyWispArtifactAsset']=export/'Assets/RoR2/Base/Artifacts/WispOnDeath/WispOnDeath.asset'
    death=read(WORK/'config/player-death-effect.json')
    if death['input_id']!=catalog['input_id'] or death['catalog_sha256']!=catalog['catalog_sha256']:
        raise RuntimeError('Player death effect catalog input changed; review query')
    roots['playerDeathEffectAsset']=export/death['location']['internalId']
    rewards=read(WORK/'config/enemy-reward-catalog.json')
    if rewards['input_id']!=catalog['input_id'] or rewards['catalog_sha256']!=catalog['catalog_sha256']:
        raise RuntimeError('Reward catalog input changed; review original query')
    if len(rewards['locations'])!=3 or any(x['type']!='UnityEngine.GameObject' for x in rewards['locations']):
        raise RuntimeError('Measured reward prefab contract changed')
    roots['enemySpawnCardAsset']=beetle/'cscBeetle.asset'
    # One measured base card, preserving the original DCCS serialization and weights.
    # Keep other actors outside this placement/timing experiment's closure.
    deck_source=export/'Assets/RoR2/Base/Scenes/golemplains/dccsGolemplainsMonsters.asset'
    deck=deck_source.read_text();card_guid=re.search(r'^guid: ([a-f0-9]{32})',Path(str(roots['enemySpawnCardAsset'])+'.meta').read_text(),re.M)[1]
    category=next(m[0] for m in re.finditer(r'^  - name: .*?\n.*?(?=^  - name: |\Z)',deck,re.M|re.S) if card_guid in m[0])
    cards=[m[0] for m in re.finditer(r'^    - spawnCardReference:\n.*?(?=^    - spawnCardReference:|^    selectionWeight:|\Z)',category,re.M|re.S) if card_guid in m[0]]
    if len(cards)!=1:raise RuntimeError('Source Beetle director card changed')
    subset=deck[:deck.index('  categories:')]+ '  categories:\n'+category.split('    cards:')[0]+'    cards:\n'+cards[0]+re.search(r'^    selectionWeight: .*$',category,re.M)[0]+'\n'
    deck_dest=stage/'EnemyClosure/DirectorBeetleSubset.asset';deck_dest.parent.mkdir(parents=True,exist_ok=True);deck_dest.write_text(subset);shutil.copy2(Path(str(deck_source)+'.meta'),Path(str(deck_dest)+'.meta'))
    director_blocks={m[1]:m[0] for m in re.finditer(r'^--- !u!\d+ &(-?\d+)\n.*?(?=^--- !u!|\Z)',scene,re.M|re.S)}
    director_component=director_blocks['9121']
    if 'fileID: 653292689, guid: 951ce57ad999ac1f040a4dceb5f8b763' not in director_component or 'm_GameObject: {fileID: 1655}' not in director_component:raise RuntimeError('Source fast director identity changed')
    director_go=re.sub(r'^  - component: \{fileID: (?!3908\}|9121\})\d+\}\n','',director_blocks['1655'],flags=re.M)
    director_dest=stage/'EnemyClosure/FastDirector.prefab';director_dest.write_text(scene[:scene.index('--- !u!')]+director_go+director_blocks['3908']+director_component)
    Path(str(director_dest)+'.meta').write_text('fileFormatVersion: 2\nguid: 8bd4270b113d42be9c081b9b702e1b80\nPrefabImporter:\n  externalObjects: {}\n  userData:\n  assetBundleName:\n  assetBundleVariant:\n')
    roots['enemyHonorArtifactAsset']=export/'Assets/RoR2/Base/Artifacts/EliteOnly/EliteOnly.asset'
    director_assets=read(WORK/'config/director-team-catalog.json')
    physics_source=export/'ProjectSettings/DynamicsManager.asset'
    physics_flags=re.findall(r'^  m_QueriesHitTriggers: ([01])$',physics_source.read_text(),re.M)
    if physics_flags!=['0']:raise RuntimeError('Original placement physics query flag changed; review before staging')
    if director_assets['input_id']!=catalog['input_id'] or director_assets['catalog_sha256']!=catalog['catalog_sha256'] or len(director_assets['locations'])!=2:raise RuntimeError('Director team catalog input changed')
    for i,row in enumerate(director_assets['locations']):roots['enemyDirectorTeamPrefab'+str(i)]=export/row['internalId']
    for i,name in enumerate(['UseAmbientLevel','BoostHp','BoostDamage']):
        roots['enemySpawnItem'+str(i)]=export/'Assets/RoR2/Base/Items'/name/(name+'.asset')
    for i,row in enumerate(rewards['locations']):roots['enemyRewardPrefab'+str(i)]=export/row['internalId']

    for name,folder in [('Poison','Base/Elites/ElitePoison'),('Haunted','Base/Elites/EliteHaunted'),('Lunar','Base/Elites/EliteLunar'),('Void','DLC1/Elites/EliteVoid')]:
        roots['enemyElite'+name]=export/('Assets/RoR2/'+folder+'/ed'+name+'.asset')
    pending=list(roots.values());seen=set();paths={};rows=[];remaps={r['from']:r['to'] for r in previous.get('ui_remaps',[])}
    while pending:
        src=pending.pop()
        if src in seen:continue
        seen.add(src);meta=Path(str(src)+'.meta');guid=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(),re.M)[1]
        if src.suffix=='.dll':
            if src.name=='UnityEngine.UI.dll' and remaps:continue
            if guid not in existing:raise RuntimeError('Unprovided enemy assembly '+src.name)
            continue
        dst=existing.get(guid,stage/'EnemyClosure'/src.relative_to(export/'Assets'))
        if guid not in existing:
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);shutil.copy2(meta,Path(str(dst)+'.meta'))
        rows.append({'source':str(src.relative_to(export)),'source_sha256':sha(src),'staged':str(dst.relative_to(WORK/'lab-project')),'reused':guid in existing,'bytes':src.stat().st_size})
        for key,value in roots.items():
            if src==value:paths[key]=str(dst.relative_to(WORK/'lab-project')).lower()
        with src.open('rb') as f:prefix=f.read(5)
        if prefix==b'%YAML':
            original=src.read_text();generated=original
            if src in [body,roots['enemyMasterAsset']]:
                root_id=re.search(r'^--- !u!1 &(-?\d+)',original,re.M)[1]
                generated=re.sub(r'(^--- !u!1 &'+root_id+r'\n.*?)(?=^--- !u!|\Z)',lambda m:re.sub(r'  m_IsActive: [01]','  m_IsActive: 0',m[0]),generated,flags=re.M|re.S)
            if guid not in existing:
                for old,new_guid in remaps.items():generated=generated.replace(old,new_guid)
                dst.write_text(generated)
            deps={g for _,g,_ in REFERENCE.findall(original) if g and not g.startswith('0000000000000000')}
            # These are measured actor skin/avatar/controller/material runtime references, not a new runtime loader.
            for dep in deps:
                if dep not in index:raise RuntimeError('Unresolved enemy GUID in '+src.name+': '+dep)
                pending.append(index[dep])
            for dep in re.findall(r'm_AssetGUID: ([a-f0-9]{32})',original):
                if dep not in runtime:raise RuntimeError('Query original catalog for enemy runtime key in '+src.name+': '+dep)
                pending.append(runtime[dep])
    recipe=read(WORK/'scene-probe-build.json');recipe['prefabAssets']=list(dict.fromkeys(recipe['prefabAssets']+[v for k,v in paths.items() if k!='playerDeathEffectAsset' and not k.startswith(('enemyRewardPrefab','enemyDirectorTeamPrefab'))]+[str(deck_dest.relative_to(WORK/'lab-project')),str(director_dest.relative_to(WORK/'lab-project'))]));recipe['playerDeathEffect']=next(r['staged'] for r in rows if r['source']==str(roots['playerDeathEffectAsset'].relative_to(export)));recipe['enemyRewardAssets']=[next(r['staged'] for r in rows if r['source']==str(roots['enemyRewardPrefab'+str(i)].relative_to(export))) for i in range(3)]+[next(r['staged'] for r in rows if r['source']==str(roots['enemyDirectorTeamPrefab'+str(i)].relative_to(export))) for i in range(2)];write(WORK/'scene-probe-build.json',recipe)
    write(out/'automatic-director-contract.json',{'source_scene_sha256':sha(export/'Assets/RoR2/Base/Scenes/golemplains/golemplains.unity'),'source_component':9121,'source_root_initially_inactive':True,'source_deck_sha256':sha(deck_source),'subset_sha256':sha(deck_dest),'director_prefab_sha256':sha(director_dest),'team_catalog':director_assets,'scope':'Original fast director natural FixedUpdate, one automatic base Beetle spawn, source credit/timing/targeting/team limit and approximate navigation placement. Owned deck retains only measured Beetle; disabled after first successful spawn; original participant/body counts follow the real registered player; no connected user/profile or full stage lifecycle. Elite catalog remains diagnostic subset; no broad elite or wave acceptance.','prior_art':'Pinned R2API.Director f539511e RunCombatDirectorsFixedUpdate distinguishes enabled Unity scheduling from explicit calls on disabled directors; DirectorAPI observes Awake/ClassicStageInfo timing. No mod hook or implementation copied.'})
    write(out/'reward-contract.json',dict(rewards,spawn_card=paths['enemySpawnCardAsset'],spawn_items=[paths['enemySpawnItem'+str(i)] for i in range(3)],reward_prefabs=[paths['enemyRewardPrefab'+str(i)] for i in range(3)],scope='Original directed CombatDirector/CharacterSpawnCard/MasterSummon and gold/timed XP; server-only, no automatic waves, client effects, level-up, logbook/profile or full Run lifecycle.'))
    write(out/'enemy-contract.json',{'roots':paths,'closure':rows,'bytes':sum(r['bytes'] for r in rows),'catalog':catalog,'prior_art':'Pinned Starstorm2 Runshroom/SS2Monster uses MonsterAssetCollection/body/model/team collision. EditorKit preserves runtime GUID/subobject separately from exported identity; original catalog resolves measured Avatar subobject. R2API.Director scene/catalog boundaries remain separate. Exact original BaseAI requires SceneInfo.GetNodeGraph and drives original InputBank/AI walker states.','scope':'Original Beetle actor/navigation/AI/skill/death integration in accepted terrain; optional audio/effects excluded on owned clones only, no DLL changes, director/progression claim or actor motion writes.'})
    write(out/'director-physics-contract.json',{'source_sha256':sha(physics_source),'source_queries_hit_triggers':False,'scope':'Only source trigger-query flag during owned original scheduling/combat probe; restore prior value in finally. Original node/collider/placement algorithms unchanged.','observation':'S141 editor original CheckPositionFree:27 eligible nodes, zero free with lab trigger queries enabled,27 with source flag false. Device acceptance remains required.'})
    return dict(paths,sourceQueriesHitTriggers=False,automaticDirector=True,enemyDirectorAsset=str(director_dest.relative_to(WORK/'lab-project')).lower(),enemyDirectorDeckAsset=str(deck_dest.relative_to(WORK/'lab-project')).lower(),enemyDirectorTeamKeys=[x['key'] for x in director_assets['locations']],enemyDirectorTeamAssets=[paths['enemyDirectorTeamPrefab'+str(i)] for i in range(2)],enemyRewards=True,enemyRewardKeys=[x['key'] for x in rewards['locations']],enemyRewardAssets=[paths['enemyRewardPrefab'+str(i)] for i in range(3)],enemySpawnItems=[paths['enemySpawnItem'+str(i)] for i in range(3)],enemySpine=True,playerDeathEffectKey=death['key'],enemyDeathItems=[paths['enemyDeathItem'+str(i)] for i in range(4)],enemyDeathEquipment=[paths['enemyDeathEquipment'+str(i)] for i in range(2)],enemyEliteAssets=[paths['enemyElite'+name] for name in ['Poison','Haunted','Lunar','Void']])

def stage_run_scene_metadata(stage,out):
    """Preserve source metadata/static references; do not load its addressed scene or diorama."""
    import shutil
    from scene_closure import REFERENCE
    export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    source=export/'Assets/RoR2/Base/Scenes/golemplains/golemplains.asset'
    text=source.read_text()
    if not all(x in text for x in ['m_Name: golemplains','sceneType: 1','stageOrder: 1','requiredExpansion: {fileID: 0}']):raise RuntimeError('Original base-stage metadata contract changed')
    index={};existing={}
    for base,target in [(export/'Assets',index),(stage,existing)]:
        for meta in base.rglob('*.meta'):
            m=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(errors='replace'),re.M)
            if m:target[m[1]]=Path(str(meta)[:-5])
    pending=[source];seen=set();rows=[];addresses=[];root=None
    while pending:
        src=pending.pop()
        if src in seen:continue
        seen.add(src);meta=Path(str(src)+'.meta');guid=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(),re.M)[1]
        if src.suffix=='.dll':
            if guid not in existing or existing[guid].name!=src.name:raise RuntimeError('Missing metadata assembly '+src.name)
            continue
        if src.suffix=='.unity':raise RuntimeError('Metadata unexpectedly imports a full scene; review closure')
        dst=existing.get(guid,stage/'RunMetadata'/src.relative_to(export/'Assets'))
        if guid not in existing:
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);shutil.copy2(meta,Path(str(dst)+'.meta'))
        if src==source:root=str(dst.relative_to(WORK/'lab-project'))
        rows.append({'source':str(src.relative_to(export)),'source_sha256':sha(src),'staged':str(dst.relative_to(WORK/'lab-project')),'reused':guid in existing,'bytes':src.stat().st_size})
        with src.open('rb') as f:prefix=f.read(5)
        if prefix==b'%YAML':
            original=src.read_text()
            for dep in {g for _,g,_ in REFERENCE.findall(original) if g and not g.startswith('0000000000000000')}:
                if dep not in index:raise RuntimeError('Missing metadata reference '+src.name+': '+dep)
                pending.append(index[dep])
            addresses.extend({'source':str(src.relative_to(export)),'key':key,'requested':False} for key in re.findall(r'm_AssetGUID: ([a-f0-9]{32})',original))
    recipe=read(WORK/'scene-probe-build.json');recipe['prefabAssets']=list(dict.fromkeys(recipe['prefabAssets']+[root]));write(WORK/'scene-probe-build.json',recipe)
    write(out/'run-metadata-closure.json',{'root':root,'closure':rows,'bytes':sum(x['bytes'] for x in rows),'unrequested_addresses':addresses,'scope':'Original base SceneDef/static metadata, preserved unchanged. No scene-address/diorama/progression/menu/native audio load. Converted static geometry retains original scene name/GUID for measured catalog identity only.'})
    return {'runSceneDefAsset':root.lower()}

def stage_barrel(stage,out,pickup=False,money=False,selection=False,drop_table=False,purchase=False,droplet_load=False,droplet_flight=False,previous=None,integrated_world=False):
    """Only the original cash-barrel static dependency closure; no generated rewards or shop logic."""
    import shutil
    from scene_closure import REFERENCE
    export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    source=export/'Assets/RoR2/Base/Interactables/Barrel1/Barrel1.prefab'
    if not all(x in source.read_text() for x in ['goldReward: 8','expReward: 4']):raise RuntimeError('Original cash barrel reward contract changed')
    index={};existing={}
    for base,target in [(export/'Assets',index),(stage,existing)]:
        for meta in base.rglob('*.meta'):
            m=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(errors='replace'),re.M)
            if m:target[m[1]]=Path(str(meta)[:-5])
    roots={'barrelAsset':source}
    if pickup:roots.update(pickupAsset=export/'Assets/RoR2/Base/Common/GenericPickup.prefab',statItemAsset=export/'Assets/RoR2/Base/Items/Syringe/Syringe.asset',junkAsset=export/'Assets/RoR2/DLC3/Items/Junk/Junk.asset')
    if money:
        chest=export/'Assets/RoR2/Base/Interactables/Chest1/Chest1.prefab';text=chest.read_text()
        if not all(x in text for x in ['costType: 1','cost: 25','automaticallyScaleCostWithDifficulty: 0','requiredUnlockable:\n','requiredExpansion: {fileID: 0}']):raise RuntimeError('Original base Chest1 cost/requirement source contract changed')
        write(out/'money-cost-source.json',{'source':str(chest.relative_to(export)),'source_sha256':sha(chest),'cost':25,'cost_type':'Money','automatic_scale':False,'scope':'Host-measured immutable source data only; no chest prefab on device.'})
        roots['multiShopCardAsset']=export/'Assets/RoR2/DLC1/Equipment/MultiShopCard/MultiShopCard.asset'
    if selection:roots.update(recycleAsset=export/'Assets/RoR2/Base/Equipment/Recycle/Recycle.asset',lowerPricedChestsAsset=export/'Assets/RoR2/DLC2/Items/LowerPricedChests/LowerPricedChests.asset')
    if drop_table:roots.update(chestDropTableAsset=export/'Assets/RoR2/Base/Interactables/Chest1/dtChest1.asset',randomlyLunarAsset=export/'Assets/RoR2/DLC1/Items/RandomlyLunar/RandomlyLunar.asset',chestLootItemAsset=export/'Assets/RoR2/Base/Items/ChainLightning/ChainLightning.asset')
    if integrated_world:
        roots['worldLunarCoinAsset']=export/'Assets/RoR2/Base/MiscPickups/LunarCoin/LunarCoin.asset'
        for key,name in [('worldGlassesAsset','CritGlasses'),('worldSlugAsset','HealWhileSafe')]:
            item=export/'Assets/RoR2/Base/Items'/name/(name+'.asset');text=item.read_text()
            if not all(x in text for x in ['unlockableDef: {fileID: 0}','requiredExpansion: {fileID: 0}','m_AssetGUID:\n','pickupModelPrefab: {fileID: ']):raise RuntimeError('Integrated unlocked direct-model item contract changed: '+name)
            roots[key]=item
    if purchase:roots.update(chestAsset=export/'Assets/RoR2/Base/Interactables/Chest1/Chest1.prefab',freeUnlockBuffAsset=export/'Assets/RoR2/DLC2/Items/OnLevelUpFreeUnlock/bdFreeUnlocks.asset',lowerPricedConsumedAsset=export/'Assets/RoR2/DLC2/Items/LowerPricedChests/LowerPricedChestsConsumed.asset',delusionArtifactAsset=export/'Assets/RoR2/CU8/Artifacts/Delusion/Delusion.asset')
    if droplet_load:roots['pickupDropletAsset']=export/'Assets/RoR2/Base/Common/PickupDroplet.prefab'
    if droplet_flight:roots['commandArtifactAsset']=export/'Assets/RoR2/Base/Artifacts/Command/Command.asset'
    pending=list(roots.values());seen=set();rows=[];paths={};root=None
    # The source chest's inactive picker panel includes recovered TranslucentImage. Its
    # measured source-only companion is compiled locally, never accepted as preserved UI.
    if purchase:pending.extend([export/'Assets/Scripts/Assembly-CSharp/LeTai/Asset/TranslucentImage/TranslucentImageSource.cs',export/'Assets/Scripts/Assembly-CSharp/TransluscentImageController.cs'])
    remaps={r['from']:r['to'] for r in (previous or {}).get('ui_remaps',[])}
    while pending:
        src=pending.pop()
        if src in seen:continue
        seen.add(src);meta=Path(str(src)+'.meta');guid=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(),re.M)[1]
        if src.suffix=='.dll':
            if src.name=='UnityEngine.UI.dll' and remaps:continue
            if guid not in existing or existing[guid].name!=src.name:raise RuntimeError('Missing interactable assembly '+src.name)
            continue
        dst=existing.get(guid,stage/'BarrelClosure'/src.relative_to(export/'Assets'))
        if guid not in existing:
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);shutil.copy2(meta,Path(str(dst)+'.meta'))
        if src==source:root=str(dst.relative_to(WORK/'lab-project'))
        for key,value in roots.items():
            if src==value:paths[key]=str(dst.relative_to(WORK/'lab-project'))
        rows.append({'source':str(src.relative_to(export)),'source_sha256':sha(src),'staged':str(dst.relative_to(WORK/'lab-project')),'reused':guid in existing,'bytes':src.stat().st_size})
        with src.open('rb') as f:prefix=f.read(5)
        if prefix==b'%YAML':
            if guid not in existing:
                generated=dst.read_text()
                for old,new in remaps.items():generated=generated.replace(old,new)
                dst.write_text(generated)
            for dep in {g for _,g,_ in REFERENCE.findall(src.read_text()) if g and not g.startswith('0000000000000000')}:
                if dep not in index:raise RuntimeError('Missing barrel reference '+src.name+': '+dep)
                pending.append(index[dep])
    recipe=read(WORK/'scene-probe-build.json');recipe['prefabAssets']=list(dict.fromkeys(recipe['prefabAssets']+[v for k,v in paths.items() if k!='pickupDropletAsset']));write(WORK/'scene-probe-build.json',recipe)
    write(out/'barrel-contract.json',{'root':root,'closure':rows,'bytes':sum(x['bytes'] for x in rows),'rollback':read(WORK/'checkpoints/LAST_KNOWN_GOOD_RUN_CLOCK.json'),'scope':'Original Barrel1 clone, original Interactor query/server dispatch, original Opening/Opened and source gold8/XP4 scaled by actual Run. Explicit no-audio owned clone and diagnostic materials. No purchase/item/drop-table/full interaction-driver/client/progression acceptance.','prior_art':'Pinned R2API.Director f539511e InteractableSpawnCardClone preserves source placement/eligibility/stage caps as distinct contracts; do not substitute manually placed barrel for director acceptance. Exact original Interactor and BarrelInteraction determine query/dispatch/rewards; no implementation copied.'})
    recipe=read(WORK/'scene-probe-build.json')
    if droplet_load:recipe['pickupDroplet']=paths['pickupDropletAsset']
    else:recipe.pop('pickupDroplet',None)
    write(WORK/'scene-probe-build.json',recipe)
    if pickup:write(out/'item-pickup-contract.json',{'roots':paths,'rollback':read(WORK/'checkpoints/LAST_KNOWN_GOOD_BARREL_INTERACTION.json'),'scope':'Original base Syringe and internal Junk definitions cataloged before inventory allocation; original CreatePickupDef/CreatePickup/half-second wait/Interactor/ItemDef.AttemptGrant/natural stats. Junk never granted and remains locked. Owned display component disabled, diagnostic source icon; no normal chest/drop/progression/profile/client pickup effects or original item model acceptance. Only original animated barrel renderer duplicated on established diagnostic view layer; original collider/query layers and accepted camera retained.','prior_art':'Pinned R2API.Items f539511e requires item registration before catalog initialization and later FindItemIndex; DebugToolkit d1e2f0aa Items.CCCreatePickup uses original UniquePickup/factory contract. Controlled spawned pickup does not establish normal item progression. No original/community implementation copied.'})
    if money:write(out/'money-cost-contract.json',{'source':read(out/'money-cost-source.json'),'roots':{'multiShopCardAsset':paths['multiShopCardAsset']},'rollback':read(WORK/'checkpoints/LAST_KNOWN_GOOD_ITEM_ACQUISITION.json'),'scope':'Uninstantiated source Chest1 cost25, original CostTypeCatalog.Init Money delegates and original empty MultiShopCard comparison. Diagnostic original GiveMoney funding17+8=25, actual player affordability/pay25/remaining0, item/equipment conservation and catalog restore. No source PurchaseInteraction callbacks/chest opening/drop/profile/progression.','prior_art':'Pinned R2API.Director f539511e InteractableSpawnCardClone separates real placement/eligibility/stage caps from diagnostic contracts. Exact legitimate CostTypeCatalog/CostTypeDef/MultiShopCardUtils establish money deduction and original equipment comparison; source Chest1 separately needs buff/item/event/drop contracts. No implementation copied.'})
    if selection:write(out/'interaction-selection-contract.json',{'rollback':read(WORK/'checkpoints/LAST_KNOWN_GOOD_ACTIVE_CLIENT.json'),'roots':paths,'scope':'Original automatic InteractionDriver target selection only with actual local ownership/source barrel and original unpaused PauseStopController. Original Recycle/LowerPricedChests comparison definitions never granted; source unlockable/expansion remain. No input/dispatch/reward effects/physical/controller/profile/platform/progression acceptance.','prior_art':'Pinned R2API.Items f539511e ItemAPI requires catalog registration before indices; R2API.Director InteractableSpawnCardClone preserves original placement/eligibility as separate from diagnostic placement. Exact original driver/Interactor/pause/outline and current source data govern this probe; no implementation copied.'})
    result={key:value.lower() for key,value in paths.items()}
    if money:result.update(moneySourceCost=25,moneySourceSha256=sha(chest))
    return result

def run_probe(physical=False,retry=False):
    from scene_runtime import movement_batch_run
    if physical:
        out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];a=read(out/'attempt.json');stage=Path(a['stage'])
        receipt=stage/'Editor/character-motor-order-result.json';order=read(receipt);expected=read(out/'original-motor-order.json')['rows'][0]['order']
        terminal=WORK/'lab-build/result.json'
        if order.get('after')!=expected or order.get('novaAfter')!=-20000 or not terminal.exists() or receipt.stat().st_mtime_ns>terminal.stat().st_mtime_ns:raise RuntimeError('Restore original motor/Nova producer order, then complete forced build before physical simulation')
    selected='body-state-spawn-state-auto-nova-spine' if physical and a.get('playable_spine') else BODY if physical else RAW
    movement_batch_run(cases=[selected],retry=physical or retry,interactive=True)

def bind():
    from device import Device
    out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];a=read(out/'attempt.json')
    mapping=read(WORK/'config/nova-input-mapping.json');source=(ROOT/mapping['observation']).resolve()
    if not source.is_relative_to(out.resolve()) or mapping['attempt']!=a['attempt']:raise RuntimeError('Stale or unrelated Nova mapping source')
    report=read(source);samples=(report.get('nova') or {}).get('observations',[])
    if not report.get('success') or report.get('phase')!='complete' or report.get('id')!=RAW or report.get('attempt')!=a['attempt']:raise RuntimeError('Incomplete/current-attempt Unity exposure required')
    axes=[mapping[key] for key in ['moveX','moveY','aimX','aimY']];buttons=[mapping[key] for key in ['jump','primary','secondary','utility','special']]
    if len(set(axes))!=4 or any(not isinstance(i,int) or not 0<=i<16 for i in axes) or len(set(buttons))!=5 or any(not isinstance(i,int) or not 0<=i<20 for i in buttons):raise RuntimeError('Invalid Nova bindings')
    if mapping.get('enableSkills') or mapping['moveYSign'] not in [-1,1] or mapping['aimYSign'] not in [-1,1]:raise RuntimeError('Movement-only mapping/sign contract changed')
    for axis in axes:
        values=[s['raw']['axes'][axis] for s in samples]
        if min(values)>-.7 or max(values)<.7:raise RuntimeError('Mapped stick axis lacks bidirectional physical evidence')
    for button in buttons:
        if not any(s['raw']['buttons'][button] for s in samples):raise RuntimeError('Mapped button lacks physical evidence')
    mapping['observation_sha256']=sha(source);target=out/'nova-input-mapping.json';write(target,mapping)
    d=Device();d.owned();runtime=read(WORK/'device/runtime.json')['persistentDataPath']
    expected='/storage/emulated/0/Android/data/dev.ror2lab.arm64/files'
    if runtime!=expected:raise RuntimeError('Unexpected lab runtime mapping destination')
    d.cmd('push',str(target),runtime+'/nova-input-mapping.json');print(json.dumps({'mapping':str(target.relative_to(ROOT)),'source_sha256':mapping['observation_sha256']}))

def current_errors(text,pid):
    """The existing lab deliberately rejects one Windows shader bundle; reject other errors."""
    lines=[line for line in text.splitlines() if re.search(r'\s'+re.escape(str(pid))+r'\s',line)]
    known=["The file can not be loaded because it was created for another build target", "Please make sure to build AssetBundles using the build target", "File's Build target is: 19", "The AssetBundle 'windows-shaders.bundle' can't be loaded"]
    failures=[]
    for i,line in enumerate(lines):
        if not re.search(r'\sE\s+(Unity|AndroidRuntime)\s*:',line):continue
        if any(message in line for message in known):continue
        if "Unknown error occurred while loading 'archive:" in line and i>0 and "File's Build target is: 19" in lines[i-1] and i+1<len(lines) and "The AssetBundle 'windows-shaders.bundle'" in lines[i+1]:continue
        failures.append(line)
    return failures
