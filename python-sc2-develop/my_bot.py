from concurrent.futures.thread import _worker
from turtle import towards
from sc2 import maps
from sc2.ids.unit_typeid import UnitTypeId
from sc2.player import Bot, Computer
from sc2.main import run_game
from sc2.data import Race, Difficulty
from sc2.bot_ai import BotAI
from sc2.game_state import GameState
from sc2.game_data import GameData
from sc2.game_info import GameInfo
from sc2.position import Point2, Point3
from sc2.unit import Unit
from sc2.units import Units
from typing import FrozenSet, Set
from loguru import logger
import random  
import numpy as np  
from sc2.ids.ability_id import AbilityId
from typing import List, Tuple
from sc2.ids.upgrade_id import UpgradeId
from sc2.ids.buff_id import BuffId
from typing import Union

firstDepotSet = 0
didBuildFirstOrbital = 0
gameStage = 0 # 0 = first wall, 1= 3 racks,upgrades,units , 2 = more racks & medivacs
 

class RushBarracks(BotAI):
     
    async def on_step(self, iteration: int):
        global firstDepotSet
        global didBuildFirstOrbital
        global gameStage
        self.upgradesDone = 0
        
        logger.level("INFO")
        if(iteration %50 == 0):
            logger.info("gameState: " + str(gameStage))
        cc : Unit = self.townhalls.first

        barracks: Units = self.structures.of_type(UnitTypeId.BARRACKS)
        refinaries: Units = self.structures.of_type(UnitTypeId.REFINERY)
        depots: Units = self.structures.of_type({UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED})

        #######################################################################
        await self.buildSCV(gasWanted = 1)
        await self.saturateRefinaries()
        await self.controlDepos()
        await self.buildDepos(cc, rushLevel = 2)

        await self.buildBarrack(cc)
        await self.buildMarines(barracks)
        
        await self.distribute_workers()
        await self.destributeAllWorkers()
        await self.buildBarracksAddons(barracks)
        await self.landBarracks()
        await self.researchBarracksUpgrades()

        ###################################################################################################################
        depot_placement_positions: FrozenSet[Point2] = self.main_base_ramp.corner_depots
        barracks_placement_position: Point2 = self.main_base_ramp.barracks_correct_placement

        if(len(depot_placement_positions) ==2 and firstDepotSet == 0 and self.time_formatted == "00:13"):
            firstDepotSet = 1
            target_depot_location: Point2 = next(iter(depot_placement_positions ))
            self.workers.gathering.closest_to(target_depot_location).move(target_depot_location)
        
        if depots: depot_placement_positions: Set[Point2] = {d for d in depot_placement_positions if depots.closest_distance_to(d) > 1}
        if self.can_afford(UnitTypeId.REFINERY) and len(depots) > 0 and len(barracks) > 0 and len(refinaries) == 0:
            #if(didBuildFirstOrbital):
            vgs = self.vespene_geyser.closer_than(10, cc)
            worker: Unit = self.select_build_worker(vgs[0])
            worker.build_gas(vgs[0])
            #else:
            #    didBuildFirstOrbital = 1
            #    await self.buildOrbitalOnMain()
        # Build depots
        await self.buildFirstDepos(cc,depots,depot_placement_positions)

        # Build barracks
        await self.buildFirstBarrack(cc,depots,barracks_placement_position)

        # upgrade barracks & future manage them 
        if(gameStage == 0):
            sp: Unit
            for sp in self.structures(UnitTypeId.BARRACKS).ready:
                if not sp.has_add_on and self.can_afford(UnitTypeId.BARRACKSREACTOR):
                    sp.build(UnitTypeId.BARRACKSREACTOR) # must add cases where cant build
                    await self.chat_send("generic build starting...")
                    gameStage = 1


        marines = self.units({UnitTypeId.MARINE, UnitTypeId.MARAUDER})
        if(self.units({UnitTypeId.MARINE, UnitTypeId.MARAUDER}).amount > 19):
            await self.microMarines(marines,cc)
            await self.useStimPack2()
        else:
            for marine in marines:
                marine.move(cc)


 
############################################### IDLE STUFF start ##################################################
    async def on_building_construction_started(self, unit: Unit):
        logger.info(f"Construction of building {unit} started at {unit.position}.")

    async def on_building_construction_complete(self, unit: Unit):
        logger.info(f"Construction of building {unit} completed at {unit.position}.")
 
    async def controlDepos(self):
        for depo in self.structures(UnitTypeId.SUPPLYDEPOT).ready:
            for unit in self.enemy_units:# Raise depos when enemies are nearby
                if unit.distance_to(depo) < 15:
                    break
            else:
                depo(AbilityId.MORPH_SUPPLYDEPOT_LOWER)
        for depo in self.structures(UnitTypeId.SUPPLYDEPOTLOWERED).ready:
            for unit in self.enemy_units: # Lower depos when no enemies are nearby
                if unit.distance_to(depo) < 10:
                    depo(AbilityId.MORPH_SUPPLYDEPOT_RAISE)
                    break

    async def buildSCV(self,gasWanted):
        logger.debug("buildSCV - called")
        cc = self.townhalls.ready.random
        if ( self.can_afford(UnitTypeId.SCV) and cc.is_idle and self.workers.amount < self.townhalls.amount * (16 + (3*gasWanted))):
            cc.train(UnitTypeId.SCV)

    async def buildDepos(self,cc,rushLevel = 1):
        logger.debug("buildDepos - called")
        if(gameStage == 0):
            return
        if ( self.supply_left < 3 and self.already_pending(UnitTypeId.SUPPLYDEPOT) == 0 and self.can_afford(UnitTypeId.SUPPLYDEPOT)):
                await self.build(UnitTypeId.SUPPLYDEPOT, near=cc.position.towards(self.game_info.map_center, 8))
        if ( self.supply_left < (3*rushLevel) and self.already_pending(UnitTypeId.SUPPLYDEPOT) <2 and self.can_afford(UnitTypeId.SUPPLYDEPOT)):
                await self.build(UnitTypeId.SUPPLYDEPOT, near=cc.position.towards(self.game_info.map_center, 8))
            
    async def saturateRefinaries(self):
        for refinery in self.gas_buildings:
            if refinery.assigned_harvesters < refinery.ideal_harvesters:
                worker: Units = self.workers.closer_than(10, refinery)
                if worker:
                    worker.random.gather(refinery)


    async def buildBarracksAddons(self,barracks):
       
        if(gameStage == 0):
            return
        for barrack in barracks.ready:
            if(not barrack.has_add_on and self.can_afford(UnitTypeId.BARRACKSTECHLAB)):
                sp: Unit
                for sp in self.structures(UnitTypeId.BARRACKS).ready.idle:
                    if not sp.has_add_on and self.can_afford(UnitTypeId.BARRACKSTECHLAB):
                        addon_points = self.barrack_points_to_build_addon(sp.position)
                        if all(self.in_map_bounds(addon_point) and self.in_placement_grid(addon_point) and self.in_pathing_grid(addon_point) for addon_point in addon_points):
                            sp.build(UnitTypeId.BARRACKSTECHLAB)
                        else:
                            sp(AbilityId.LIFT)

    async def barrack_land_positions(self,sp_position: Point2) -> List[Point2]:
            land_positions = [(sp_position + Point2((x, y))).rounded for x in range(-1, 2) for y in range(-1, 2)]
            return land_positions + self.barrack_points_to_build_addon(sp_position)

    async def landBarracks(self):
        for sp in self.structures(UnitTypeId.BARRACKSFLYING).idle:
            possible_land_positions_offset = sorted(
                (Point2((x, y)) for x in range(-10, 10) for y in range(-10, 10)),
                key=lambda point: point.x**2 + point.y**2,
            )
            offset_point: Point2 = Point2((-0.5, -0.5))
            possible_land_positions = (sp.position.rounded + offset_point + p for p in possible_land_positions_offset)
            for target_land_position in possible_land_positions:
                land_and_addon_points: List[Point2] = await self.barrack_land_positions(target_land_position)
                if all(
                    self.in_map_bounds(land_pos) and self.in_placement_grid(land_pos)
                    and self.in_pathing_grid(land_pos) for land_pos in land_and_addon_points
                ):
                    sp(AbilityId.LAND, target_land_position)
                    break

    async def buildBarrack(self,cc):
        logger.debug("buildBarrack - called")
        if(gameStage != 1):
            return
        if (self.can_afford(UnitTypeId.BARRACKS) and self.structures(UnitTypeId.BARRACKS).amount < 3):
            await self.build(UnitTypeId.BARRACKS, near=cc.position.towards(self.game_info.map_center, 8))

    async def destributeAllWorkers(self):
        if(gameStage > 0):
            await self.distribute_workers()

    async def buildMarines(self,barracks):
        for barrack in barracks.ready:
            if(barrack.has_add_on and barrack.add_on_tag in self.techlab_tags and self.can_afford(UnitTypeId.MARAUDER) and barrack.is_idle):
                barrack.train(UnitTypeId.MARAUDER)
            else:
                if(barrack.has_add_on and barrack.add_on_tag not in self.techlab_tags and self.can_afford(UnitTypeId.MARINE) and barrack.is_idle):
                    barrack.train(UnitTypeId.MARINE)
                    barrack.train(UnitTypeId.MARINE)

    async def microMarines(self,marines,cc):
        enemy_location = self.enemy_start_locations[0]
        for marine in marines:
            if(marine.weapon_cooldown == 0):
                marine.attack(enemy_location)
            else:
                if(self.enemy_units.amount > 20):
                    marine.move(cc)

    async def useStimPack2(self):
        for unit in self.units({UnitTypeId.MARINE, UnitTypeId.MARAUDER}): 
            if (self.already_pending_upgrade(UpgradeId.STIMPACK) == 1 and not unit.has_buff(BuffId.STIMPACK) and not unit.has_buff(BuffId.STIMPACKMARAUDER) and unit.health > 60):
                for enemy in self.enemy_units:# Raise depos when enemies are nearby
                    if enemy.distance_to(unit) < 15:
                        unit(AbilityId.EFFECT_STIM_MARINE)
                        break

    async def useStimPack(self):
        self.client.game_step = 2
        for unit in self.units({UnitTypeId.MARINE, UnitTypeId.MARAUDER}): 
            if self.enemy_units:
                # attack (or move towards) zerglings / banelings
                if unit.weapon_cooldown <= self.client.game_step / 2:
                    enemies_in_range = self.enemy_units.filter(unit.target_in_range)
                    # attack lowest hp enemy if any enemy is in range
                    if enemies_in_range:
                        # Use stimpack
                        if (
                            self.already_pending_upgrade(UpgradeId.STIMPACK) == 1
                            and not unit.has_buff(BuffId.STIMPACK) and unit.health > 10
                        ):
                            unit(AbilityId.BARRACKSTECHLABRESEARCH_STIMPACK)

                        # attack baneling first
                        filtered_enemies_in_range = enemies_in_range.of_type(UnitTypeId.BANELING)

                        if not filtered_enemies_in_range:
                            filtered_enemies_in_range = enemies_in_range.of_type(UnitTypeId.ZERGLING)
                        # attack lowest hp unit
                        lowest_hp_enemy_in_range = min(filtered_enemies_in_range, key=lambda u: u.health)
                        unit.attack(lowest_hp_enemy_in_range)

                    # no enemy is in attack-range, so give attack command to closest instead
                    else:
                        closest_enemy = self.enemy_units.closest_to(unit)
                        unit.attack(closest_enemy)

                # move away from zergling / banelings
                else:
                    stutter_step_positions = self.position_around_unit(unit, distance=4)

                    # filter in pathing grid
                    stutter_step_positions = {p for p in stutter_step_positions if self.in_pathing_grid(p)}

                    # find position furthest away from enemies and closest to unit
                    enemies_in_range = self.enemy_units.filter(lambda u: unit.target_in_range(u, -0.5))

                    if stutter_step_positions and enemies_in_range:
                        retreat_position = max(
                            stutter_step_positions,
                            key=lambda x: x.distance_to(enemies_in_range.center) - x.distance_to(unit),
                        )
                        unit.move(retreat_position)

                    else:
                        logger.info(f"No retreat positions detected for unit {unit} at {unit.position.rounded}.")
    def position_around_unit(
        self,
        pos: Union[Unit, Point2, Point3],
        distance: int = 1,
        step_size: int = 1,
        exclude_out_of_bounds: bool = True,
    ):
        pos = pos.position.rounded
        positions = {
            pos.offset(Point2((x, y)))
            for x in range(-distance, distance + 1, step_size) for y in range(-distance, distance + 1, step_size)
            if (x, y) != (0, 0)
        }
        # filter positions outside map size
        if exclude_out_of_bounds:
            positions = {
                p
                for p in positions
                if 0 <= p[0] < self.game_info.pathing_grid.width and 0 <= p[1] < self.game_info.pathing_grid.height
            }
        return positions
############################################# IDLE STUFF end #######################################
    async def researchBarracksUpgrades(self):
        if(self.upgradesDone == 1):
            return
        techLabs : Units = self.structures(UnitTypeId.BARRACKSTECHLAB)
        for techLab in techLabs.ready.idle:
            if self.already_pending_upgrade(UpgradeId.STIMPACK) == 0 and self.can_afford(UpgradeId.STIMPACK):
                logger.info("building STIMPACK ..........")
                techLab.research(UpgradeId.STIMPACK)
            if self.already_pending_upgrade(UpgradeId.STIMPACK) > 0 and self.can_afford(UpgradeId.SHIELDWALL):
                logger.info("building combat shield ..........")
                techLab.research(UpgradeId.SHIELDWALL)
                self.upgradesDone = 1

    def barrack_points_to_build_addon(self,sp_position: Point2) -> List[Point2]:
        addon_offset: Point2 = Point2((2.5, -0.5))
        addon_position: Point2 = sp_position + addon_offset
        addon_points = [
            (addon_position + Point2((x - 0.5, y - 0.5))).rounded for x in range(0, 2) for y in range(0, 2)
        ]
        return addon_points


    async def buildOrbitalOnMain(self):
        if(gameStage != 0):
            return
        orbital_tech_requirement: float = self.tech_requirement_progress(UnitTypeId.ORBITALCOMMAND)
        if orbital_tech_requirement == 1:
            # Loop over all idle command centers (CCs that are not building SCVs or morphing to orbital)
            for cc in self.townhalls(UnitTypeId.COMMANDCENTER).idle:
                # Check if we have 150 minerals; this used to be an issue when the API returned 550 (value) of the orbital, but we only wanted the 150 minerals morph cost
                if self.can_afford(UnitTypeId.ORBITALCOMMAND):
                    cc(AbilityId.UPGRADETOORBITAL_ORBITALCOMMAND)
                    didBuildFirstOrbital = 1

    async def buildFirstBarrack(self,cc,depots,barracks_placement_position):
        logger.debug("buildFirstBarrack - called")
        if(gameStage != 0):
            return
        if(self.structures(UnitTypeId.BARRACKS).amount > 0 or self.already_pending(UnitTypeId.BARRACKS) > 0):
            return
        if depots.ready and self.can_afford(UnitTypeId.BARRACKS):
            workers = self.workers
            if workers and barracks_placement_position:  # if workers were found
                worker: Unit = workers.furthest_to(cc)
                worker.build(UnitTypeId.BARRACKS, barracks_placement_position)

    async def buildFirstDepos(self,cc,depots,depot_placement_positions):
        if(gameStage != 0):
            return
        #logger.info("---------------- corners:" + str(len(depot_placement_positions)) +  " depos: " + str(len(depots)))
        if self.can_afford(UnitTypeId.SUPPLYDEPOT) and self.already_pending(UnitTypeId.SUPPLYDEPOT) == 0:
            if len(depot_placement_positions) == 0:
                return
            if len(depot_placement_positions) == 1:
                workers: Units = self.workers.gathering
                target_depot_location: Point2 = depot_placement_positions.pop()
                worker: Unit = workers.closest_to(depots[0])
                worker.build(UnitTypeId.SUPPLYDEPOT, target_depot_location)
                return
            target_depot_location: Point2 = depot_placement_positions.pop()
            workers: Units = self.workers
            if workers:  # if workers were found
                worker: Unit = workers.furthest_to(cc)
                worker.build(UnitTypeId.SUPPLYDEPOT, target_depot_location)

    async def buildFirstExpansion(self):
            # Expand if we can afford (400 minerals) and have less than 2 bases
        if (1 <= self.townhalls.amount < 2 and self.already_pending(UnitTypeId.COMMANDCENTER) == 0 and self.can_afford(UnitTypeId.COMMANDCENTER)):
            # get_next_expansion returns the position of the next possible expansion location where you can place a command center
            location: Point2 = await self.get_next_expansion()
            if location:
                # Now we "select" (or choose) the nearest worker to that found location
                worker: Unit = self.select_build_worker(location)
                if worker and self.can_afford(UnitTypeId.COMMANDCENTER):
                    # The worker will be commanded to build the command center
                    worker.build(UnitTypeId.COMMANDCENTER, location)
#build marine before reactor, after 3 rack, rush racks, only builds 1 marine
_map = random.choice(
    [
        # Most maps have 2 upper points at the ramp (len(self.main_base_ramp.upper) == 2)
        "AutomatonLE",
        "BlueshiftLE",
        "CeruleanFallLE",
        "KairosJunctionLE",
        "ParaSiteLE",
        "PortAleksanderLE",
        "StasisLE",
        "ParaSiteLE",  # Has 5 upper points at the main ramp
        "AcolyteLE",  # Has 4 upper points at the ramp to the in-base natural and 2 upper points at the small ramp
        #"HonorgroundsLE",  # Has 4 or 9 upper points at the large main base ramp
    ]
)
run_game(
    #maps.get("HonorgroundsLE"),
    maps.get("ParaSiteLE"),
    #maps.get(_map),
    [Bot(Race.Terran, RushBarracks()), Computer(Race.Zerg, Difficulty.VeryHard)],
    realtime=False,
    # sc2_version="4.10.1",
)

#class WorkerRushBot(BotAI):
#    async def on_step(self, iteration: int):
#        if iteration == 0:
#            for worker in self.workers:
#                worker.attack(self.enemy_start_locations[0])

# name='VeryEasy'   name='Easy'  name='Medium'   name='MediumHard'  name='Hard' name='Harder'  name='VeryHard'   name='CheatVision'  name='CheatMoney'  name='CheatInsane'


# ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER)
# if not ccs:
#     return
# cc: Unit = ccs.first


#enable worker resquedule
 #await self.distribute_workers()