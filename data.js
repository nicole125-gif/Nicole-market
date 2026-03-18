// ═══════════════════════════════════════════════════════════
//  STRATEGIC DASHBOARD — CENTRAL DATA STORE
//  Edit this file OR use /admin to update content visually
//  Last structure update: 2026-02
// ═══════════════════════════════════════════════════════════

window.MARKET_DATA = {
  meta: {
    lastUpdated: "2026-02-28",
    updatedBy: "Nicole",
    version: "2.1"
  },

  // ── MACRO PAGE ───────────────────────────────────────────
  macro: {
    headline: "中国宏观脉搏",
    subline: "基于"十五五"规划开局之年的精密流体市场环境分析",
    period: "十五五规划开局年 / FY-2026",
    summaryStats: [
      { label: "综合景气度", value: "Expansionary" },
      { label: "政策向量",   value: "Targeted Easing" },
      { label: "外部压力指数", value: "Moderate" },
      { label: "数字经济比重", value: "43.7%" }
    ],
    metrics: [
      {
        label: "GDP 增速", labelEn: "GDP GROWTH",
        value: 5.0, unit: "%", trend: "+0.2%",
        insight: "结构性增长优于规模扩张",
        color: "#00FFB2",
        sparkData: [4.6, 4.8, 5.0], years: ["2024","2025","2026E"],
        note: "GDP 目标值 5.0% 来源于国家统计局公报及中金宏观研究团队预测。",
        actions: [
          { tag: "Q1", text: "完成重点晶圆客户年框合同续签，锁定 Q2–Q3 备货需求" },
          { tag: "Q2", text: "联动液冷集成商预演 2026 扩容节点，提前部署冷却阀组样品" },
          { tag: "H2", text: "布局生物医药园区本地化服务站，缩短响应链路至 48H" }
        ]
      },
      {
        label: "工业增加值", labelEn: "IND. VALUE ADD",
        value: 6.2, unit: "%", trend: "↑ Upward",
        insight: "新质生产力贡献率超 35%",
        color: "#00C8FF",
        sparkData: [5.1, 5.7, 6.2], years: ["2024","2025","2026E"],
        note: "工业增加值数据来源于国家统计局月度数据，德勤白皮书提供数字化转型量化分析。",
        actions: [
          { tag: "立即", text: "梳理先进封装 TOP 15 客户，建立超纯水阀组专项产品组合" },
          { tag: "Q2",  text: "与动力电池热管理集成商联合定义比例控制阀技术规格书" },
          { tag: "Q3",  text: "在长三角/珠三角工业园区推进流体诊断服务包订阅模式试点" }
        ]
      },
      {
        label: "制造业固投", labelEn: "MFG. CAPEX",
        value: 11.4, unit: "%", trend: "Stable",
        insight: "数字化转型进入产线深水区",
        color: "#FFD700",
        sparkData: [9.2, 10.8, 11.4], years: ["2024","2025","2026E"],
        note: "制造业固定资产投资数据引自国家统计局固投月报，麦肯锡报告提供行业拆解。",
        actions: [
          { tag: "战略", text: "建立制造业固投项目预警数据库，锁定 6 个月前采购决策窗口" },
          { tag: "产品", text: "推出智能工厂流体控制套件（含 IO-Link 数字接口）" },
          { tag: "渠道", text: "与系统集成商签署优先供应协议，覆盖华东/华南重点工业园区" }
        ]
      },
      {
        label: "出口增速", labelEn: "EXPORT GROWTH",
        value: 4.8, unit: "%", trend: "Shift",
        insight: "高附加值组件替代传统代工",
        color: "#FF6B35",
        sparkData: [5.9, 4.2, 4.8], years: ["2024","2025","2026E"],
        note: "出口增速数据来源于商务部月度贸易统计，商务部研究院提供出口结构升级分析。",
        actions: [
          { tag: "品牌", text: "联合半导体设备商打造「洁净流体合规出口」联合解决方案白皮书" },
          { tag: "服务", text: "在东南亚/中东布局本地化备件库，支持随主机出海的售后服务" },
          { tag: "认证", text: "加速推进 SEMI F57/F19 认证体系，提升客户出口竞争力背书" }
        ]
      },
      {
        label: "PPI 走势", labelEn: "PPI TREND",
        value: 1.2, unit: "%", trend: "Recovery",
        insight: "中下游利润空间重构",
        color: "#BF80FF",
        sparkData: [-2.7, -0.8, 1.2], years: ["2024","2025","2026E"],
        note: "PPI 数据来源于国家统计局价格统计司，中金宏观团队提供 PPI 回升路径预测。",
        actions: [
          { tag: "定价", text: "基于 PPI 回升重新校准产品定价策略，推出 ROI 可视化计算工具" },
          { tag: "价值", text: "将「降耗增效」纳入核心销售话术，量化流体控制精度带来的节省数据" },
          { tag: "时机", text: "把握利润修复窗口，推进存量客户设备升级与服务合同升级谈判" }
        ]
      }
    ]
  },

  // ── LIQUID COOLING PAGE ──────────────────────────────────
  liquid: {
    headline: "AI Infrastructure",
    subline: "算力密度突破物理极限，流体控制成为 AI 基础设施的关键变量",
    eyebrow: "SBU · AI Infrastructure · Liquid Cooling",
    marketRows: [
      { label: "新建智算中心液冷渗透率", value: "45%",    note: "↑ +16pp vs 2025", color: "#00FFB2" },
      { label: "国家级枢纽 PUE 准入",    value: "< 1.15", note: "法规强制执行",     color: "#00C8FF" },
      { label: "CDU 市场规模 CAGR",     value: "47%",    note: "2024–2028E",      color: "#FFD700" }
    ],
    bodyText: "在 AI 算力集群（新一代 Blackwell 架构）功率密度突破 100kW/机柜背景下，流体控制的绝对可靠性已成为算力基建的「第一优先级」变量。",
    roadmap: [
      { year: "2026", title: "精密动态平衡", color: "#00FFB2", desc: "基于 AI 负载的毫秒级流量调节，响应延迟 <5ms" },
      { year: "2027", title: "预测性维护",   color: "#00C8FF", desc: "自诊断执行器接入 DCIM，故障预警窗口达 72H" },
      { year: "2028", title: "相变冷却突破", color: "#BF80FF", desc: "两相流高压气密控制，散热密度突破 300W/cm²" }
    ],
    swot: [
      { tag: "ADVANTAGE",   zh: "核心优势", color: "#00FFB2", text: "基于全球领先的无泄漏（Zero-Leakage）密封技术，卡位高附加值二次侧流量均衡控制，替代壁垒极高。" },
      { tag: "OPPORTUNITY", zh: "战略机遇", color: "#00C8FF", text: "AI 训练集群功率密度突破 100kW/机柜，CDU 出货量 CAGR 83%，精密流量控制窗口期在 2026–2027 完全打开。" },
      { tag: "THREAT",      zh: "潜在威胁", color: "#FF6B35", text: "本土系统集成商自研低端零部件的「系统化替代」，需从单一零件销售转向系统模块化方案，缩短决策链路。" }
    ]
  },

  // ── SEMICONDUCTOR PAGE ───────────────────────────────────
  semicon
