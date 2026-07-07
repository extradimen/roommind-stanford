"""Seed default LLM config, scenario, characters, and dispatch rules."""

from sqlalchemy import select

from app.database import async_session_factory
from app.models.db import CharacterTemplate, DispatchRule, LLMConfig, ScenarioTemplate
from app.orchestrator.defaults import default_orchestration_config, merge_orchestration_config


from app.platform_llm import ensure_platform_llm_defaults, resolve_active_model, save_platform_llm_settings


async def seed_if_empty() -> None:
    async with async_session_factory() as db:
        result = await db.execute(select(LLMConfig).limit(1))
        if result.scalar_one_or_none():
            return

        llm = LLMConfig(
            name="default",
            provider="siliconflow",
            model="moonshotai/Kimi-K2.5",
            temperature=0.7,
            max_tokens=2048,
            is_active=True,
        )
        db.add(llm)

        scenario = ScenarioTemplate(
            slug="supply-chain-negotiation",
            title="供应链价格谈判",
            description="你作为采购方代表，在会议室与供应商 CEO 和法务进行价格和交货期谈判。",
            business_goal="将单价压至 85 元以下，交货期不超过 30 天，同时维持良好合作关系",
            phases=["opening", "discovery", "bargaining", "closing"],
            win_conditions=[
                {"field": "price", "operator": "<=", "value": 85},
                {"field": "delivery_days", "operator": "<=", "value": 30},
                {"field": "relationship_score", "operator": ">=", "value": 60},
            ],
            scene_config={
                "environment": "meeting_room",
                "lighting": "office_day",
                "camera": "first_person",
                "spawn": "seat_user",
            },
            director_prompt=None,
            router_rules={},
            orchestration_config=default_orchestration_config(),
            is_published=True,
        )
        db.add(scenario)
        await db.flush()

        characters = [
            CharacterTemplate(
                scenario_id=scenario.id,
                character_id="supplier_ceo",
                display_name="王总（供应商 CEO）",
                persona="强势但注重长期关系，说话直接，偶尔用数据支撑观点",
                responsibility="守住价格底线，争取有利付款条件",
                tendency={"risk": "low", "aggression": "high", "cooperation": "medium"},
                private_state={
                    "real_floor_price": 82,
                    "cost_pressure": "原材料上涨5%",
                    "negotiation_agenda": [
                        {"item": "确认本次采购量", "target": "锁定年度框架协议≥10万件", "priority": 1},
                        {"item": "守住单价底线", "target": "单价≥88元，理想≥95元", "priority": 2},
                        {"item": "争取账期条件", "target": "预付30%，余款30天内结清", "priority": 3},
                    ],
                    "opening_move": "先主动提出确认采购量，再谈价格",
                    "redlines": ["单价不接受低于82元", "不接受无上限违约条款"],
                },
                spawn_point="seat_opposite",
                avatar_manifest={"color": "#4a90d9", "height": 1.75},
                sort_order=0,
            ),
            CharacterTemplate(
                scenario_id=scenario.id,
                character_id="legal_counsel",
                display_name="李律师（法务）",
                persona="严谨、关注条款细节，说话谨慎",
                responsibility="审核合同条款，提示法律风险",
                tendency={"risk": "very_low", "aggression": "low", "cooperation": "high"},
                private_state={
                    "hidden_clause_risk": "不可抗力条款对供应商有利",
                    "negotiation_agenda": [
                        {"item": "审查违约条款", "target": "将违约金上限写入合同≤合同总额5%", "priority": 1},
                        {"item": "明确交货期罚则", "target": "逾期每日罚款不超过0.05%", "priority": 2},
                    ],
                    "opening_move": "等价格谈完后插入合同条款议题",
                    "redlines": ["不接受连带赔偿责任", "不接受无限期保修条款"],
                },
                spawn_point="seat_side",
                avatar_manifest={"color": "#7b68ee", "height": 1.68},
                sort_order=1,
            ),
            CharacterTemplate(
                scenario_id=scenario.id,
                character_id="procurement_ally",
                display_name="张经理（内部采购同事）",
                persona="数据驱动，善于压价，是你的内部盟友",
                responsibility="提供市场数据支持，协助压价策略",
                tendency={"risk": "medium", "aggression": "medium", "cooperation": "high"},
                private_state={"market_benchmark": 83},
                spawn_point="seat_adjacent",
                avatar_manifest={"color": "#50c878", "height": 1.7},
                sort_order=2,
            ),
        ]
        for c in characters:
            db.add(c)

        rules = [
            DispatchRule(
                scenario_id=scenario.id,
                name="价格话题",
                description="用户提到价格、报价、成本时，供应商 CEO 优先发言",
                trigger_keywords=["价格", "报价", "单价", "成本", "多少钱", "折扣"],
                priority_character_ids=["supplier_ceo", "procurement_ally"],
                min_speakers=1,
                max_speakers=2,
                weights={"relevance": 0.5, "responsibility": 0.4},
                is_active=True,
            ),
            DispatchRule(
                scenario_id=scenario.id,
                name="合同条款",
                description="用户提到合同、条款、法律时，法务优先",
                trigger_keywords=["合同", "条款", "法律", "律师", "李律师", "违约", "赔偿", "协议"],
                priority_character_ids=["legal_counsel"],
                min_speakers=1,
                max_speakers=1,
                is_active=True,
            ),
            DispatchRule(
                scenario_id=scenario.id,
                name="交货与物流",
                description="交货期、物流相关话题",
                trigger_keywords=["交货", "交付", "物流", "工期", "延期", "发货"],
                priority_character_ids=["supplier_ceo", "procurement_ally"],
                min_speakers=1,
                max_speakers=2,
                is_active=True,
            ),
        ]
        for r in rules:
            db.add(r)

        await db.commit()


async def sync_scenario_orchestration_config() -> None:
    """Ensure existing scenarios have default orchestration config."""
    async with async_session_factory() as db:
        result = await db.execute(select(ScenarioTemplate))
        changed = False
        for scenario in result.scalars().all():
            merged = merge_orchestration_config(scenario.orchestration_config)
            if scenario.orchestration_config != merged:
                scenario.orchestration_config = merged
                changed = True
        if changed:
            await db.commit()


async def sync_dispatch_rule_keywords() -> None:
    """Patch seed dispatch rules when keywords are extended."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(DispatchRule).where(DispatchRule.name == "合同条款")
        )
        rule = result.scalar_one_or_none()
        if not rule:
            return
        desired = ["合同", "条款", "法律", "律师", "李律师", "违约", "赔偿", "协议"]
        if rule.trigger_keywords != desired:
            rule.trigger_keywords = desired
            await db.commit()


async def sync_llm_config_with_platform() -> None:
    """Align DB LLM row with openclaw-style platform.json defaults."""
    async with async_session_factory() as db:
        result = await db.execute(select(LLMConfig).where(LLMConfig.is_active.is_(True)).limit(1))
        cfg = result.scalar_one_or_none()
        if not cfg:
            return
        if cfg.provider == "ollama_cloud":
            cfg.provider = "ollama"
        provider, model = resolve_active_model(cfg.provider, cfg.model)
        cfg.provider = provider
        cfg.model = model
        save_platform_llm_settings(provider=provider, model_id=model)
        await db.commit()
