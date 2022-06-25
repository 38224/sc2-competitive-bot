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


firstDepotSet = 0
didBuildFirstOrbital = 0
gameStage = 0 # 0 = first wall, 1= 3 racks,upgrades,units , 2 = more racks & medivacs

class RushBarracks(BotAI):
     
    async def on_step(self, iteration: int):
        global firstDepotSet
        global didBuildFirstOrbital
        global gameStage
        logger.level("INFO")
        logger.info("gameState: " + str(gameStage))
        cc : Unit = self.townhalls.first

        barracks: Units = self.structures.of_type(UnitTypeId.BARRACKS)
        refinaries: Units = self.structures.of_type(UnitTypeId.REFINERY)
        depots: Units = self.structures.of_type({UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED})

        #######################################################################
        await self.buildSCV(gasWanted = 1)
        await self.saturateRefinaries()
        await self.controlDepos()
        await self.buildDepos(cc)

        await self.buildBarrack(cc)
        await self.buildMarines(barracks)
        await self.destributeAllWorkers()
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

        if(self.units(UnitTypeId.MARINE).amount > 9):
            marines = self.units(UnitTypeId.MARINE)
            for marine in marines:
                marine.attack(self.enemy_start_locations[0])
 
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
        if ( self.can_afford(UnitTypeId.SCV) and cc.is_idle and self.workers.amount < self.townhalls.amount * (19 + (3*gasWanted))):
            cc.train(UnitTypeId.SCV)

    async def buildDepos(self,cc):
        logger.debug("buildDepos - called")
        if(gameStage == 0):
            return
        if ( self.supply_left < 3 and self.already_pending(UnitTypeId.SUPPLYDEPOT) == 0 and self.can_afford(UnitTypeId.SUPPLYDEPOT)):
            await self.build(UnitTypeId.SUPPLYDEPOT, near=cc.position.towards(self.game_info.map_center, 8))
            
    async def saturateRefinaries(self):
        for refinery in self.gas_buildings:
            if refinery.assigned_harvesters < refinery.ideal_harvesters:
                worker: Units = self.workers.closer_than(10, refinery)
                if worker:
                    worker.random.gather(refinery)


    async def buildMarines(self,barracks):
        for barrack in barracks.ready:
            if(not barrack.has_add_on and self.can_afford(UnitTypeId.BARRACKSREACTOR)):
                barrack.build(UnitTypeId.BARRACKSREACTOR)
            if(self.can_afford(UnitTypeId.MARINE) and barrack.is_idle and barrack.has_add_on):
                barrack.train(UnitTypeId.MARINE)
                barrack.train(UnitTypeId.MARINE)

    async def buildBarrack(self,cc):
        logger.debug("buildBarrack - called")
        if(gameStage != 1):
            return
        if (self.can_afford(UnitTypeId.BARRACKS) and self.structures(UnitTypeId.BARRACKS).amount < 3):
            await self.build(UnitTypeId.BARRACKS, near=cc.position.towards(self.game_info.map_center, 8))

    async def destributeAllWorkers(self):
        if(gameStage > 0):
            self.distribute_workers()
############################################# IDLE STUFF end #######################################



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
    [Bot(Race.Terran, RushBarracks()), Computer(Race.Zerg, Difficulty.Hard)],
    realtime=True,
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