# 注：该策略仅供参考和学习，不保证收益。

#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 策略代码总共分为三大部分,1)PARAMS变量 2)initialize函数 3)handle_data函数
# 请根据指示阅读。或者直接点击运行回测按钮,进行测试,查看策略效果。

# 策略名称：均值回归策略
# 策略详细介绍：https://wequant.io/study/strategy.mean_reversion.html
# 关键词：价格波动、短期策略。
# 方法：
# 1)用一定回看时间范围内的均值作为基础,构建价格上下双轨;
# 2)当价格突破上轨时,卖出; 价格突破下轨时,买入。

import numpy as np


# 阅读1,首次阅读可跳过:
# PARAMS用于设定程序参数,回测的起始时间、结束时间、滑点误差、初始资金和持仓。
# 可以仿照格式修改,基本都能运行。如果想了解详情请参考新手学堂的API文档。
PARAMS = {
    "start_time": "2016-10-01 00:00:00",  # 回测起始时间
    "end_time": "2017-07-01 00:00:00",  # 回测结束时间
    "commission": 0.002,  # 此处设置交易佣金
    "slippage": 0.001,  # 此处设置交易滑点
    "account_initial": {"huobi_cny_cash": 100000,
                      "huobi_cny_btc": 0},  # 设置账户初始状态
}


# 阅读2,遇到不明白的变量可以跳过,需要的时候回来查阅:
# initialize函数是两大核心函数之一（另一个是handle_data）,用于初始化策略变量。
# 策略变量包含：必填变量,以及非必填（用户自己方便使用）的变量
def initialize(context):
    # 设置回测频率, 可选："1m", "5m", "15m", "30m", "60m", "4h", "1d", "1w"
    context.frequency = "1d"
    # 设置回测基准, 比特币："huobi_cny_btc", 莱特币："huobi_cny_ltc", 以太坊："huobi_cny_eth"
    context.benchmark = "huobi_cny_btc"
    # 设置回测标的, 比特币："huobi_cny_btc", 莱特币："huobi_cny_ltc", 以太坊："huobi_cny_eth"
    context.security = "huobi_cny_btc"

    # 设置策略参数
    # 计算移动均值所需的历史bar数目,用户自定义的变量,可以被handle_data使用
    context.user_data.sma_window_size = 5
    # 用户自定义的变量,可以被handle_data使用,当前价格低于buy_threshold*SMA, 触发买信号
    context.user_data.buy_threshold = 0.9
    # 用户自定义的变量,可以被handle_data使用,当前价格高于sell_threshold*SMA,触发卖信号
    context.user_data.sell_threshold = 1.2
    # 止损线,用户自定义的变量,可以被handle_data使用
    context.user_data.portfolio_stop_loss = 0.75
    # 用户自定义变量,记录下是否已经触发止损
    context.user_data.stop_loss_triggered = False


# 阅读3,策略核心逻辑：
# handle_data函数定义了策略的执行逻辑,按照frequency生成的bar依次读取并执行策略逻辑,直至程序结束。
# handle_data和bar的详细说明,请参考新手学堂的解释文档。
def handle_data(context):
    # 如果已经触发了止损,则不进行任何操作
    if context.user_data.stop_loss_triggered:
        context.log.warn("已触发止损线, 此bar不会有任何指令 ... ")
        return

    # 检查是否到达强制平仓线,如果是,强制平仓,并结束所有操作
    if context.account.huobi_cny_net < context.user_data.portfolio_stop_loss * context.account_initial.huobi_cny_net:
        context.log.warn(
            "当前净资产:%.2f 位于止损线下方 (%f), 初始资产:%.2f, 触发止损动作" % (
            context.account.huobi_cny_net, context.user_data.portfolio_stop_loss, context.account_initial.huobi_cny_net))

        context.user_data.stop_loss_triggered = True
        context.log.info("设置 stop_loss_triggered（已触发止损信号）为真")

        # 强平,卖出所有持仓
        if context.account.huobi_cny_btc >= HUOBI_CNY_BTC_MIN_ORDER_QUANTITY:
            # 以市价单卖出所有持仓
            context.log.info("stop loss selling huobi_cny_btc")
            context.order.sell(context.security, quantity=str(context.account.huobi_cny_btc))
        return

    # 获取历史数据,取后sma_window_size根bar
    hist = context.data.get_price(context.security, count=context.user_data.sma_window_size, frequency=context.frequency)
    if len(hist.index) < context.user_data.sma_window_size:
        context.log.warn("bar的数量不足, 等待下一根bar...")
        return

    # 计算短均线值
    sma = np.mean(hist["close"][-1 * context.user_data.sma_window_size:])

    # 取得最新价格
    latest_close_price = context.data.get_current_price(context.security)

    # 计算上下双轨
    lower = sma * context.user_data.buy_threshold
    upper = sma * context.user_data.sell_threshold

    context.log.info("当前 最新价格 = %s, 均值 = %s, 上轨 = %s, 下轨 = %s" % (latest_close_price, sma, upper, lower))

    # 计算买入卖出信号
    if latest_close_price < lower:
        context.log.info("价格跌破下轨,产生买入信号")
        if context.account.huobi_cny_cash >= HUOBI_CNY_BTC_MIN_ORDER_CASH_AMOUNT:
            # 有买入信号,且持有现金,则市价单全仓买入
            context.log.info("正在买入 %s" % context.security)
            context.log.info("下单金额为 %s 元" % context.account.huobi_cny_cash)
            context.order.buy(context.security, cash_amount=str(context.account.huobi_cny_cash))
        else:
            context.log.info("现金不足，无法下单")
    elif latest_close_price > upper:
        context.log.info("价格突破下轨,产生卖出信号")
        if context.account.huobi_cny_btc >= HUOBI_CNY_BTC_MIN_ORDER_QUANTITY:
            # 有卖出信号,且持有仓位,则市价单全仓卖出
            context.log.info("正在卖出 %s" % context.security)
            context.log.info("卖出数量为 %s" % context.account.huobi_cny_btc)
            context.order.sell(context.security, quantity=str(context.account.huobi_cny_btc))
        else:
            context.log.info("仓位不足，无法卖出")
    else:
        context.log.info("无交易信号，进入下一根bar")