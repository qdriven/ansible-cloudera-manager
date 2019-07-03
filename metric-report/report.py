# -*- coding:utf-8 -*-
import datetime
import os
import sys
import string
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as dt
import pylab as pl
import pygal
import heapq
#import cairosvg
import ssh

from common.timeseries import TimeSeriesQuery
from cm_api.endpoints.timeseries import *
from cm_api.endpoints.types import ApiList
from utils.getConfig import get_conf
from utils.sendmail import sendmail
from utils.utc import utc2local
import utils.getDate
from utils.line_model import get_linear_model
from pygal.style import LightGreenStyle

reload(sys)
sys.setdefaultencoding('utf-8')

# 解决Matplotlib中文问题
pl.mpl.rcParams['font.sans-serif'] = ['SimHei'] #指定默认字体
pl.mpl.rcParams['axes.unicode_minus'] = False   #解决保存图像是负号'-
#邮箱配置
FROM = get_conf("mail","FROM")
TO = string.splitfields(get_conf("mail","TO"),',')
SUBJECT = get_conf("mail","SUBJECT")+ datetime.datetime.now().strftime('%Y-%m-%d')

CAPTION = get_conf("pic","caption")
CAPTIONCPU = get_conf("pic","captionCPU")
CAPTIONMEM = get_conf("pic","captionMEM")
CAPTIONNET = get_conf("pic","captionNET")
filenameCPU = get_conf("pic","filenameCPU")
filenameMEM = get_conf("pic","filenameMEM")
filenameNET = get_conf("pic","filenameNET")
SUFIX= get_conf("pic","SUFIX")
# WIDTH = get_conf("pic","WIDTH")
# HEIGHT = get_conf("pic","HEIGHT")

#数据粒度，用于图表时间显示的单位（例如天、小时等）的判断
class Granularity:
    RAW = 1  # every 1 Seconds
    TEN_MINUTES = 10  # every 10 minutes(100Seconds）
    HOURLY = 600  # every 600 Seconds
    SIX_HOURS = 3600  # every 6 hours(3600Seconds)
    DAILY = 14400  # every 14400 Seconds
    WEEKLY = 100800  # every 100800 Seconds
    #AUTO = -1


def do_query(query, from_time, to_time):
  responseList = []
  tsquery = TimeSeriesQuery()
  for response in tsquery.query(query, from_time, to_time):
      responseList.append(response)
  return responseList

def do_query_rollup(query, from_time, to_time,desired_rollup, must_use_desired_rollup):
  responseList = []
  tsquery = TimeSeriesQuery()
  for response in tsquery.query_rollup(query, from_time, to_time,desired_rollup, must_use_desired_rollup):
      responseList.append(response)
  return responseList

# 获取日报
def getReportChart(query,from_time,to_time,caption,filename,granularity,desired_rollup, must_use_desired_rollup):
  # if ((Granularity.RAW == granularity) or (Granularity.TEN_MINUTES == granularity)):
  #   caption = caption + ' (' + from_time.strftime('%Y%m%d') + ')'  # 日报标题
  # else:
  #   caption = caption + ' (' + from_time.strftime('%Y%m%d') + '--' + to_time.strftime('%Y%m%d') + ')'  # 周报标题

  fileName = filename + ".png"
  plt.style.use('ggplot')
  plt.figure(figsize=(14, 4))
  maxY = 0  # Y轴最大值
  type = 'SAMPLE'  # 数据类型，用于判断是否是计算变量还是原始变量
  responseList = do_query_rollup(query, from_time, to_time,desired_rollup, must_use_desired_rollup)
  for response in responseList:
    if response.timeSeries:
      for ts in response.timeSeries:
        x = []
        yMax = []
        yMean = []
        metadata = ts.metadata
        unit = metadata.unitNumerators[0].encode("utf-8")
        y_title = unit
        for data in ts.data:
          x_label = utc2local(data.timestamp).strftime("%Y-%m-%d %H:%M:%S")
          x_time = datetime.datetime.strptime(x_label, "%Y-%m-%d %H:%M:%S")
          x.append(x_time)
          if (None != data.aggregateStatistics):
            yMax.append(data.aggregateStatistics.max)
          yMean.append(data.value)
          type = data.type
        legend = metadata.entityName
        if (legend == u'成都综合生产集群'):
          code = '-'
        elif (legend == u'成都公共服务集群'):
          code = ':'
        elif (legend == u'成都准实时生产集群'):
          code = '--'
        else:
          code = '-.'
        if ([] != yMax):
          labelMax = legend + "Max"
	  # print labelMax
          pl.plot_date(x, yMax, label=labelMax, linestyle=code, linewidth=1)
        labelAvg = legend + "Avg"
        pl.plot_date(x, yMean, label=labelAvg, linestyle=code, linewidth=1)
        #   line_chart1.add(code + "--Max", yMax,stroke_style={'width': 2, 'dasharray': '1, 3', 'linecap': 'round', 'linejoin': 'round'})
        # line_chart1.add(code + "--Avg", yMean)
        # pl.plot_date(x, y, label=legend, linestyle=code, linewidth=1)
        if ([] != yMax):
          maxY = max(maxY, max(yMax))
        maxY = max(maxY, max(yMean))

  # X轴时间显示格式
  ax = pl.gca()
  if ((Granularity.RAW == granularity) or (Granularity.TEN_MINUTES == granularity)):
    xfmt = dt.DateFormatter('%H:%M')
  elif (Granularity.HOURLY == granularity):
    xfmt = dt.DateFormatter('%m-%d %H:%M')
  else:
    xfmt = dt.DateFormatter('%y-%m-%d')
  ax.xaxis.set_major_formatter(xfmt)
  pl.gcf().autofmt_xdate()
  # Y轴单位，例如50%，100%
  if ('SAMPLE' == type):
    # 如果是原始变量，直接根据单位设置Y轴单位后缀
    if ('percent' == unit):
      maxYTick = maxY
      suffix = '%'  # 单位后缀
    elif ('bytes' == unit):
      if (maxY > 1024 * 1024 * 1024 * 1024):
        maxYTick = maxY / 1024 / 1024 / 1024 / 1024
        suffix = 'T'
      if (maxY > 1024 * 1024 * 1024):
        maxYTick = maxY / 1024 / 1024 / 1024
        suffix = 'G'
      elif (maxY > 1024 * 1024):
        maxYTick = maxY / 1024 / 1024
        suffix = 'M'
      elif (maxY > 1024):
        maxYTick = maxY / 1024
        suffix = 'K'  # 网络流量单位转换
      else:
        maxYTick = maxY
        suffix = 'b'
  else:
    # 如果是计算变量，默认设置
    maxYTick = maxY
    suffix = '%'
  y_ticks = [0, 0.5 * maxY, maxY]
  y_tickslabels = ['0', "%.1f" % (0.5 * maxYTick) + suffix, "%.1f" % (maxYTick) + suffix]
  ax.set_yticks(y_ticks)
  ax.set_yticklabels(y_tickslabels)
  pl.title(caption)
  pl.legend(loc='best', fontsize=7)
  pl.grid(True)
  pl.ylabel(y_title)
  pl.savefig(fileName)
  pl.cla()
  return fileName


#生成HDFS环比报告-周环比（表格和对应趋势图,按周、月、季度统计）
def getHDFSWeekHistory(query,from_time,to_time,caption,granularity,desired_rollup, must_use_desired_rollup,dfstotal,dfsRemaining):
  html = []
  x_labels = []
  dict = {}
  maxY = 0  # Y轴最大值
  type = 'SAMPLE'  # 数据类型，用于判断是否是计算变量还是原始变量
  unit = None
  rollupUsed = None

  if ((Granularity.RAW == granularity) or (Granularity.TEN_MINUTES == granularity)):
    caption = caption + ' (' + from_time.strftime('%m%d') + ')'  # 日报标题
  else:
    caption = caption + ' (' + from_time.strftime('%m%d') + '--' + to_time.strftime('%m%d') + ')'  # 周报标题
  # fileName = caption + SUFIX

  responseList = do_query_rollup(query, from_time, to_time,desired_rollup, must_use_desired_rollup)
  for response in responseList:
    if response.timeSeries:
      for ts in response.timeSeries:
        x = []
        y = []
        metadata = ts.metadata
        rollupUsed = metadata.rollupUsed
        unit = metadata.unitNumerators[0].encode("utf-8")
        y_title = metadata.metricName + "(" + metadata.unitNumerators[0].encode("utf-8") + ")"
        for data in ts.data:
          type = data.type
          if ((Granularity.RAW == granularity) or (Granularity.TEN_MINUTES == granularity)):
            label = utc2local(data.timestamp).strftime("%H:%M:%S")
          elif ((Granularity.HOURLY == granularity) or (Granularity.SIX_HOURS == granularity)):
            label = utc2local(data.timestamp).strftime("%H:%M")
          else:
            label = utc2local(data.timestamp).strftime("%m-%d")
          x_labels.append(label)
          y.append(data.value)
          key = metadata.entityName
          value = data.value
          dict.setdefault(key, []).append(value)
        maxY = max(maxY, max(y))

  maxY = max(maxY,1024 * 1024 * 1024 * 1024 * 1024)

  # Y轴单位，例如50%，100%
  if ('SAMPLE' == type):
    # 如果是原始变量，直接根据单位设置Y轴单位后缀
    if ('percent' == unit):
      maxYTick = maxY
      suffix = '%'  # 单位后缀
    elif ('bytes' == unit):
      # 网络流量单位转换
      if (maxY > 1024 * 1024 * 1024 * 1024):
        maxYTick = maxY / 1024 / 1024 / 1024 / 1024
        suffix = 'T'
      elif (maxY > 1024 * 1024 * 1024):
        maxYTick = maxY / 1024 / 1024 / 1024
        suffix = 'G'
      elif (maxY > 1024 * 1024):
        maxYTick = maxY / 1024 / 1024
        suffix = 'M'
      elif (maxY > 1024):
        maxYTick = maxY / 1024
        suffix = 'K'
      else:
        maxYTick = maxY
        suffix = 'b'
  else:
    # 如果是计算变量，默认设置
    maxYTick = maxY
    suffix = '%'

  valListWeek = []
  timeListWeek = []
  increList = []
  totalSize = 0
  list = dict.values()
  if(len(list) > 0 and len(list[0]) > 0):
    if(rollupUsed == u'DAILY'):
      valListWeek = list[0][::-6]  # 按时间由近及远排列
      timeListWeek = x_labels[::-6]
    elif(rollupUsed == u'WEEKLY'):
      valListWeek = list[0][::-1]  # 按时间由近及远排列
      timeListWeek = x_labels[::-1]
    if (rollupUsed == 'DAILY' or rollupUsed == 'WEEKLY'):
      html.append(
      "<br/><br/>周增长情况<br><table bgcolor=#F9F9F9 border=1 cellspacing=0><tr><th>日期</th><th>已用容量(T)</th><th>上周容量(T)</th><th>增量(T)</th><th>周增长率(%)</th><th>趋势图</th></tr>")
    for i in range(len(valListWeek) - 1):
      currVal = valListWeek[i]
      lastWeekVal = valListWeek[i + 1]
      html.append("<tr><td>")
      html.append(timeListWeek[i])
      html.append("</td><td>")
      html.append('%.2f' % (currVal / 1024 / 1024 / 1024 / 1024))
      html.append("</td><td>")
      html.append('%.2f' % (lastWeekVal / 1024 / 1024 / 1024 / 1024))
      html.append("</td><td>")
      html.append('%.2f' % ((currVal - lastWeekVal) / 1024 / 1024 / 1024 / 1024))
      increList.append((currVal - lastWeekVal) / 1024 / 1024 / 1024 / 1024)
      html.append("</td><td>")
      if (int(lastWeekVal) != 0):
        html.append('%.2f' % (100 * (currVal - lastWeekVal)/ lastWeekVal))
      html.append("</td>")
      if (0 == i):
        html.append("<td rowspan=" + str(len(valListWeek)) + "><img src=cid:id0></td>")
      html.append("</tr>")
    html.append("</table>")
    maxsize = 0
    for size in increList[0:4]:
      maxsize = max(size,maxsize)
    dfstotal = dfstotal / 1024 / 1024 / 1024 / 1024
    dfsRemaining = dfsRemaining / 1024 / 1024 / 1024 / 1024
    daysRemaining1 = "%.1f" %((dfstotal * 0.7 - (dfstotal - dfsRemaining) )/ maxsize * 7)
    X_parameters = []
    Y_parameters = []
    for val in list[0]:
      X_parameters.append([val / 1024 / 1024 / 1024 / 1024])
    for i in range(len(X_parameters)):
      Y_parameters.append(i)
    predictions = get_linear_model(X_parameters,Y_parameters,dfstotal * 0.7)
    daysRemaining2 = predictions[0] - len(Y_parameters)
    remark = "说明：按最近增长速度，预计还有<font color=red>" + "%.1f" % min(daysRemaining1,daysRemaining2) + "</font>天到达70%的警戒线<br/>"
    html.append(remark)

    line_chart1 = pygal.Bar(width=800, height=300)
    line_chart1.x_labels = timeListWeek[::-1]
    line_chart1.add('hdfs', valListWeek[::-1])
    line_chart1.y_title = unit
    # 设置Y轴演示标签
    line_chart1.y_labels = [
      {'label': 'O', 'value': 0},
      {'label': "%.1f" % (0.25 * maxYTick) + suffix, 'value': 0.25 * maxY},
      {'label': "%.1f" % (0.5 * maxYTick) + suffix, 'value': 0.5 * maxY},
      {'label': "%.1f" % (0.75 * maxYTick) + suffix, 'value': 0.75 * maxY},
      {'label': "%.1f" % (maxYTick) + suffix, 'value': maxY}]
    line_chart1.render_to_png('hdfsweek.png')
  report = ''.join(html)
  return report


# 生成HDFS环比报告-月环比（表格和对应趋势图,按周、月、季度统计）
def getHDFSMonthHistory(query, from_time, to_time, caption, granularity, desired_rollup, must_use_desired_rollup):
  html = []
  x_labels = []
  dict = {}
  maxY = 0  # Y轴最大值
  type = 'SAMPLE'  # 数据类型，用于判断是否是计算变量还是原始变量
  unit = None
  rollupUsed = None

  if ((Granularity.RAW == granularity) or (Granularity.TEN_MINUTES == granularity)):
    caption = caption + ' (' + from_time.strftime('%m%d') + ')'  # 日报标题
  else:
    caption = caption + ' (' + from_time.strftime('%m%d') + '--' + to_time.strftime('%m%d') + ')'  # 周报标题
  # fileName = caption + SUFIX

  responseList = do_query_rollup(query, from_time, to_time, desired_rollup, must_use_desired_rollup)
  for response in responseList:
    if response.timeSeries:
      for ts in response.timeSeries:
        x = []
        y = []
        metadata = ts.metadata
        rollupUsed = metadata.rollupUsed
        unit = metadata.unitNumerators[0].encode("utf-8")
        y_title = metadata.metricName + "(" + metadata.unitNumerators[0].encode("utf-8") + ")"
        for data in ts.data:
          type = data.type
          if ((Granularity.RAW == granularity) or (Granularity.TEN_MINUTES == granularity)):
            label = utc2local(data.timestamp).strftime("%H:%M:%S")
          elif ((Granularity.HOURLY == granularity) or (Granularity.SIX_HOURS == granularity)):
            label = utc2local(data.timestamp).strftime("%H:%M")
          else:
            label = utc2local(data.timestamp).strftime("%m-%d")
          x_labels.append(label)
          y.append(data.value)
          key = metadata.entityName
          value = data.value
          dict.setdefault(key, []).append(value)
        maxY = max(maxY, max(y))

  maxY = max(maxY, 1024 * 1024 * 1024 * 1024 * 1024)

  # Y轴单位，例如50%，100%
  if ('SAMPLE' == type):
    # 如果是原始变量，直接根据单位设置Y轴单位后缀
    if ('percent' == unit):
      maxYTick = maxY
      suffix = '%'  # 单位后缀
    elif ('bytes' == unit):
      # 网络流量单位转换
      if (maxY > 1024 * 1024 * 1024 * 1024):
        maxYTick = maxY / 1024 / 1024 / 1024 / 1024
        suffix = 'T'
      elif (maxY > 1024 * 1024 * 1024):
        maxYTick = maxY / 1024 / 1024 / 1024
        suffix = 'G'
      elif (maxY > 1024 * 1024):
        maxYTick = maxY / 1024 / 1024
        suffix = 'M'
      elif (maxY > 1024):
        maxYTick = maxY / 1024
        suffix = 'K'
      else:
        maxYTick = maxY
        suffix = 'b'
  else:
    # 如果是计算变量，默认设置
    maxYTick = maxY
    suffix = '%'

  list = dict.values()
  if (len(list) > 0 and len(list[0]) > 0):
    timeListMonth = []
    valListMonth = []
    if (rollupUsed == 'DAILY'):
      valListMonth = list[0][::-30]  # 按时间由近及远排列
      timeListMonth = x_labels[::-30]
    elif (rollupUsed == 'WEEKLY'):
      valListMonth = list[0][::-4]  # 按时间由近及远排列
      timeListMonth = x_labels[::-4]
    if (rollupUsed == 'DAILY' or rollupUsed == 'WEEKLY'):
      html.append(
        "<br>月增长情况<br><table bgcolor=#F9F9F9 border=1 cellspacing=0><tr><th>日期</th><th>已用容量(T)</th><th>上月容量(T)</th><th>增量(T)</th><th>月增长率(%)</th><th>趋势图</th></tr>")
      for i in range(len(valListMonth) - 1):
        currVal = valListMonth[i]
        lastMonthVal = valListMonth[i + 1]
        html.append("<tr><td>")
        html.append(timeListMonth[i])
        html.append("</td><td>")
        html.append('%.2f' % (currVal / 1024 / 1024 / 1024 / 1024))
        html.append("</td><td>")
        html.append('%.2f' % (lastMonthVal / 1024 / 1024 / 1024 / 1024))
        html.append("</td><td>")
        html.append('%.2f' % ((currVal - lastMonthVal) / 1024 / 1024 / 1024 / 1024))
        html.append("</td><td>")
        if (int(lastMonthVal) != 0):
          html.append('%.2f' % (100 * (currVal - lastMonthVal) / lastMonthVal))
        html.append("</td>")
        if (0 == i):
          html.append("<td rowspan=" + str(len(valListMonth)) + "><img src=cid:id1></td>")
        html.append("</tr>")
      html.append("</table>")
    line_chart2 = pygal.Bar(width=800, height=300)
    line_chart2.x_labels = timeListMonth[::-1]
    line_chart2.add('hdfs', valListMonth[::-1])
    line_chart2.y_title = unit
    line_chart2.y_labels = [
      {'label': 'O', 'value': 0},
      {'label': "%.1f" % (0.25 * maxYTick) + suffix, 'value': 0.25 * maxY},
      {'label': "%.1f" % (0.5 * maxYTick) + suffix, 'value': 0.5 * maxY},
      {'label': "%.1f" % (0.75 * maxYTick) + suffix, 'value': 0.75 * maxY},
      {'label': "%.1f" % (maxYTick) + suffix, 'value': maxY}]
    line_chart2.render_to_png('hdfsmonth.png')

  report = ''.join(html)
  return report


# 生成HDFS环比报告-季度环比（表格和对应趋势图,按周、月、季度统计）
def getHDFSQtrHistory(query, from_time, to_time, caption, granularity, desired_rollup, must_use_desired_rollup):
  html = []
  x_labels = []
  dict = {}
  maxY = 0  # Y轴最大值
  type = 'SAMPLE'  # 数据类型，用于判断是否是计算变量还是原始变量
  unit = None
  rollupUsed = None

  if ((Granularity.RAW == granularity) or (Granularity.TEN_MINUTES == granularity)):
    caption = caption + ' (' + from_time.strftime('%m%d') + ')'  # 日报标题
  else:
    caption = caption + ' (' + from_time.strftime('%m%d') + '--' + to_time.strftime('%m%d') + ')'  # 周报标题
  # fileName = caption + SUFIX

  responseList = do_query_rollup(query, from_time, to_time, desired_rollup, must_use_desired_rollup)
  for response in responseList:
    if response.timeSeries:
      for ts in response.timeSeries:
        x = []
        y = []
        metadata = ts.metadata
        rollupUsed = metadata.rollupUsed
        unit = metadata.unitNumerators[0].encode("utf-8")
        y_title = metadata.metricName + "(" + metadata.unitNumerators[0].encode("utf-8") + ")"
        for data in ts.data:
          type = data.type
          if ((Granularity.RAW == granularity) or (Granularity.TEN_MINUTES == granularity)):
            label = utc2local(data.timestamp).strftime("%H:%M:%S")
          elif ((Granularity.HOURLY == granularity) or (Granularity.SIX_HOURS == granularity)):
            label = utc2local(data.timestamp).strftime("%H:%M")
          else:
            label = utc2local(data.timestamp).strftime("%m-%d")
          x_labels.append(label)
          y.append(data.value)
          key = metadata.entityName
          value = data.value
          dict.setdefault(key, []).append(value)
        maxY = max(maxY, max(y))

  maxY = max(maxY, 1024 * 1024 * 1024 * 1024 * 1024)

  # Y轴单位，例如50%，100%
  if ('SAMPLE' == type):
    # 如果是原始变量，直接根据单位设置Y轴单位后缀
    if ('percent' == unit):
      maxYTick = maxY
      suffix = '%'  # 单位后缀
    elif ('bytes' == unit):
      # 网络流量单位转换
      if (maxY > 1024 * 1024 * 1024 * 1024):
        maxYTick = maxY / 1024 / 1024 / 1024 / 1024
        suffix = 'T'
      elif (maxY > 1024 * 1024 * 1024):
        maxYTick = maxY / 1024 / 1024 / 1024
        suffix = 'G'
      elif (maxY > 1024 * 1024):
        maxYTick = maxY / 1024 / 1024
        suffix = 'M'
      elif (maxY > 1024):
        maxYTick = maxY / 1024
        suffix = 'K'
      else:
        maxYTick = maxY
        suffix = 'b'
  else:
    # 如果是计算变量，默认设置
    maxYTick = maxY
    suffix = '%'

  list = dict.values()
  if (len(list) > 0 and len(list[0]) > 0):
    timeListQtr = []
    valListQtr = []
    if (rollupUsed == 'DAILY'):
      valListQtr = list[0][::-90]  # 按时间由近及远排列
      timeListQtr = x_labels[::-90]
    elif (rollupUsed == 'WEEKLY'):
      valListQtr = list[0][::-12]  # 按时间由近及远排列
      timeListQtr = x_labels[::-12]
    if (rollupUsed == 'DAILY' or rollupUsed == 'WEEKLY'):
      html.append(
        "<br>季度增长情况<br><table bgcolor=#F9F9F9 border=1 cellspacing=0><tr><th>日期</th><th>已用容量(T)</th><th>上季度容量(T)</th><th>增量(T)</th><th>季度增长率(%)</th><th>趋势图</th></tr>")
      for i in range(len(valListQtr) - 1):
        currVal = valListQtr[i]
        lastQrtVal = valListQtr[i + 1]
        html.append("<tr><td>")
        html.append(timeListQtr[i])
        html.append("</td><td>")
        html.append('%.2f' % (currVal / 1024 / 1024 / 1024 / 1024))
        html.append("</td><td>")
        html.append('%.2f' % (lastQrtVal / 1024 / 1024 / 1024 / 1024))
        html.append("</td><td>")
        html.append('%.2f' % ((currVal - lastQrtVal) / 1024 / 1024 / 1024 / 1024))
        html.append("</td><td>")
        if (int(lastQrtVal) != 0):
          html.append('%.2f' % (100 * (currVal - lastQrtVal) / lastQrtVal))
        html.append("</td>")
        if (0 == i):
          html.append("<td rowspan=" + str(len(valListQtr)) + "><img src=cid:id2></td>")
        html.append("</tr>")
      html.append("</table>")

    line_chart3 = pygal.Bar(width=800, height=300)
    line_chart3.x_labels = timeListQtr[::-1]
    line_chart3.add('hdfs', valListQtr[::-1])
    line_chart3.y_title = unit
    line_chart3.y_labels = [
      {'label': 'O', 'value': 0},
      {'label': "%.1f" % (0.25 * maxYTick) + suffix, 'value': 0.25 * maxY},
      {'label': "%.1f" % (0.5 * maxYTick) + suffix, 'value': 0.5 * maxY},
      {'label': "%.1f" % (0.75 * maxYTick) + suffix, 'value': 0.75 * maxY},
      {'label': "%.1f" % (maxYTick) + suffix, 'value': maxY}]
    line_chart3.render_to_png('hdfsquarter.png')

  report = ''.join(html)
  return report

def getJobCount(query,from_time,to_time):
  jobCount = 0
  responseList = do_query(query, from_time, to_time)
  for response in responseList:
    if response.timeSeries:
      for ts in response.timeSeries:
        for data in ts.data:
          jobCount +=1
  return jobCount

def getImpalaJobSummary(from_time,to_time):
  query_1min_count = "select  query_duration from IMPALA_QUERIES where serviceName=impala AND (query_state=FINISHED OR query_state=EXCEPTION)  and query_duration <= 60000.0"
  query_5min_count = "select  query_duration from IMPALA_QUERIES where serviceName=impala AND (query_state=FINISHED OR query_state=EXCEPTION)  and query_duration > 60000.0 and query_duration <= 300000.0"
  query_15min_count = "select  query_duration from IMPALA_QUERIES where serviceName=impala AND (query_state=FINISHED OR query_state=EXCEPTION)  and query_duration > 300000.0 and query_duration <= 900000.0"
  query_30min_count = "select  query_duration from IMPALA_QUERIES where serviceName=impala AND (query_state=FINISHED OR query_state=EXCEPTION)  and query_duration > 900000.0 and query_duration <= 1800000.0"
  query_60min_count = "select  query_duration from IMPALA_QUERIES where serviceName=impala AND (query_state=FINISHED OR query_state=EXCEPTION)  and query_duration > 1800000.0 and query_duration <= 3600000.0"
  query_120min_count = "select  query_duration from IMPALA_QUERIES where serviceName=impala AND (query_state=FINISHED OR query_state=EXCEPTION)  and query_duration > 3600000.0 and query_duration <= 7200000.0"
  query_120min_plus_count = "select query_duration from IMPALA_QUERIES where serviceName=impala AND (query_state=FINISHED OR query_state=EXCEPTION)  and query_duration > 7200000.0"

  job_1min_count = getJobCount(query_1min_count,from_time,to_time)
  job_5min_count = getJobCount(query_5min_count, from_time, to_time)
  job_15min_count = getJobCount(query_15min_count, from_time, to_time)
  job_30min_count = getJobCount(query_30min_count, from_time, to_time)
  job_60min_count = getJobCount(query_60min_count, from_time, to_time)
  job_120min_count = getJobCount(query_120min_count, from_time, to_time)
  job_120min_plus_count = getJobCount(query_120min_plus_count, from_time, to_time)
  job_total = job_1min_count + job_5min_count + job_15min_count + job_30min_count + job_60min_count + job_120min_count + job_120min_plus_count

  # plt.figure(figsize=(11,5))
  # types = '0-1m','1-5m', '5-15m', '15-30m', '30-60m', '60-120m', '>120m'
  # X = [job_1min_count, job_5min_count, job_15min_count, job_30min_count,job_60min_count,job_120min_count,job_120min_plus_count]
  # COUNT = []
  # labels = []
  # for i in range(min(len(types), len(X))):
  #   if(X[i] != 0):
  #     COUNT.append(X[i])
  #     labels.append(types[i] + ':' + str(X[i]))
  # plt.axes(aspect=1)  # set this , Figure is round, otherwise it is an ellipse
  # plt.pie(x=COUNT, labels=labels, labeldistance=1.1, autopct='%3.1f %%', startangle=90,shadow=False,pctdistance=0.6)
  # plt.title("Total Count:" + str(job_total))
  # pie_chart_name = "impalaJobSummary.png"
  # plt.legend(loc='best', fontsize=8)
  # plt.show()
  # plt.savefig(pie_chart_name)
  # plt.cla()
  types = '0-1m','1-5m', '5-15m', '15-30m', '30-60m', '60-120m', '>120m'
  X = [job_1min_count, job_5min_count, job_15min_count, job_30min_count, job_60min_count, job_120min_count,job_120min_plus_count]
  pie_chart = pygal.Pie(width=800,height=400)
  pie_chart.title = "Total Count:" + str(job_total)
  for i in range(min(len(types), len(X))):
    if (X[i] != 0):
      label = types[i] + ':' + str(X[i]) + ' ' + "%.1f" % ((float)(X[i]) / job_total * 100) + '%'
      pie_chart.add(label, X[i])
  pie_chart_name = "impalaJobSummary.png"
  pie_chart.render_to_png(pie_chart_name)
  return pie_chart_name

def getHiveJobSummary(from_time,to_time):
  query_5min_count = "select application_duration from YARN_APPLICATIONS where service_name = \"yarn\" and hive_query_id RLIKE \".*\" and application_duration <= 300000.0 "
  query_15min_count = "select application_duration from YARN_APPLICATIONS where service_name = \"yarn\" and hive_query_id RLIKE \".*\" and application_duration > 300000.0 and application_duration <= 1500000.0 "
  query_30min_count = "select application_duration from YARN_APPLICATIONS where service_name = \"yarn\" and hive_query_id RLIKE \".*\" and application_duration > 1500000.0 and application_duration <= 3000000.0 "
  query_60min_count = "select application_duration from YARN_APPLICATIONS where service_name = \"yarn\" and hive_query_id RLIKE \".*\" and application_duration > 3000000.0 and application_duration <= 6000000.0 "
  query_120min_count = "select application_duration from YARN_APPLICATIONS where service_name = \"yarn\" and hive_query_id RLIKE \".*\" and application_duration > 6000000.0 and application_duration <= 12000000.0 "
  query_120min_plus_count = "select application_duration from YARN_APPLICATIONS where service_name = \"yarn\" and hive_query_id RLIKE \".*\" and application_duration > 12000000.0 "

  job_5min_count = getJobCount(query_5min_count, from_time, to_time)
  job_15min_count = getJobCount(query_15min_count, from_time, to_time)
  job_30min_count = getJobCount(query_30min_count, from_time, to_time)
  job_60min_count = getJobCount(query_60min_count, from_time, to_time)
  job_120min_count = getJobCount(query_120min_count, from_time, to_time)
  job_120min_plus_count = getJobCount(query_120min_plus_count, from_time, to_time)
  job_total =  job_5min_count + job_15min_count + job_30min_count + job_60min_count + job_120min_count + job_120min_plus_count

  # plt.figure(figsize=(11, 5))
  # types = '1-5m', '5-15m', '15-30m', '30-60m', '60-120m', '>120m'
  # X = [job_5min_count, job_15min_count, job_30min_count, job_60min_count, job_120min_count,job_120min_plus_count]
  # COUNT = []
  # labels = []
  # for i in range(min(len(types), len(X))):
  #   if (X[i] != 0):
  #     COUNT.append(X[i])
  #     labels.append(types[i] + ':' + str(X[i]) + ',' + str("%.1f" % X[i]/job_total))
  # plt.axes(aspect=1)  # set this , Figure is round, otherwise it is an ellipse
  # patches, l_text, p_text = plt.pie(x=COUNT, labels=labels, labeldistance=1.0,autopct='%3.1f %%',startangle = 90,shadow=False,pctdistance = 0.6)
  # for t in l_text:
  #   t.set_size = (20)
  # for t in p_text:
  #   t.set_size = (15)
  # plt.title("Total Count:" + str(job_total))
  # pie_chart_name = "hiveJobSummary.png"
  # plt.legend(loc='best', fontsize=8)
  # plt.savefig(pie_chart_name)
  # plt.cla()
  types = '1-5m', '5-15m', '15-30m', '30-60m', '60-120m', '>120m'
  X = [job_5min_count, job_15min_count, job_30min_count, job_60min_count, job_120min_count,job_120min_plus_count]
  pie_chart = pygal.Pie(width=800,height=400)
  pie_chart.title = "Total Count:" + str(job_total)
  for i in range(min(len(types), len(X))):
    if (X[i] != 0):
      label = types[i] + ':' + str(X[i]) + ' ' + "%.1f" % ((float)(X[i])/job_total * 100) + '%'
      pie_chart.add(label,X[i])
  pie_chart_name = "hiveJobSummary.png"
  pie_chart.render_to_png(pie_chart_name)
  return pie_chart_name


#生成Impala Top20报告
def getImpalaTop20(query,from_time,to_time,caption,granularity):
  h = []
  attrs = ['user','database','query_duration','thread_cpu_time','hdfs_bytes_read','memory_accrual','memory_aggregate_peak','category','executing','service_name','coordinator_host_id','stats_missing','statement','entityName','pool']

  html = []
  html.append("<br><br><table bgcolor=#F9F9F9 border=1 cellspacing=0><tr>")
  html.append("<td>time</td>")
  for attr in attrs:
    html.append("<td>")
    html.append(attr)
    if('query_duration' == attr):
      html.append("(ms)")
    html.append("</td>")
  html.append("</tr>")

  responseList = do_query(query, from_time, to_time)
  for response in responseList:
    if response.timeSeries:
      for ts in response.timeSeries:
        metadata = ts.metadata
        for data in ts.data:
          line = []
          if metadata.attributes:
            line.append("<tr>")
            line.append("<td>")
            line.append(utc2local(data.timestamp).strftime("%m-%d %H:%M:%S"))
            line.append("</td>")
            for attr in attrs:
              line.append("<td>")
              if metadata.attributes.has_key(attr):
                attrVal = metadata.attributes[attr]
                # 自动转换时长单位
                if ('query_duration' == attr):
                  if((int)(attrVal) > 60 * 60 * 1000):
                    attrVal = ('%.2f' % ((float)(attrVal) / 60 / 60 / 1000)) + "h" # 小时
                  elif ((int)(attrVal) > 60 * 1000):
                    attrVal = (str)((int)(attrVal) / 60 / 1000) + "m" # 分
                  elif ((int)(attrVal) > 1000):
                    attrVal = (str)((int)(attrVal) / 1000)  + "s"# 秒
                if ('hdfs_bytes_read' == attr):
                  if((float)(attrVal) > 1024 * 1024 * 1024):
                    attrVal = ('%.2f' % ((float)(attrVal) / 1024 / 1024 / 1024)) + "G"
                  elif ((float)(attrVal) > 1024 * 1024):
                    attrVal = ('%.2f' % ((float)(attrVal) / 1024 / 1024 )) + "M"
                  elif ((float)(attrVal) > 1024):
                    attrVal = ('%.2f' % ((float)(attrVal) / 1024 )) + "K"
                if (('memory_accrual' == attr) or ('memory_aggregate_peak' == attr)):
                  if((float)(attrVal) > 8 * 1024 * 1024 * 1024):
                    attrVal = ('%.2f' % ((float)(attrVal) / 8 / 1024 / 1024 / 1024)) + "G"
                  elif ((float)(attrVal) > 8 * 1024 * 1024):
                    attrVal = ('%.2f' % ((float)(attrVal) / 8 / 1024 / 1024)) + "M"
                  elif ((float)(attrVal) > 8 * 1024):
                    attrVal = ('%.2f' % ((float)(attrVal) / 8 / 1024)) + "K"
                line.append(attrVal)
              else:
                line.append('N/A')
              line.append("</td>")
            line.append("</tr>")
            heapq.heappush(h,(data.value,line))  #根据时长进行堆排序，Push的格式为(duration,<tr><td>attr1<td>...td>attrN<td></tr>)
  top20 = sorted(h, reverse=True)[0:20]
  for item in top20:
    html += item.__getitem__(1)
  html.append("</table>")
  report = ''.join(html)
  return report

#生成Hive Top20报告
def getHive20(query,from_time,to_time,caption,granularity):
  h = []
  attrs = ['user','name','application_duration','cpu_milliseconds','mb_millis','hdfs_bytes_read','category','service_name','entityName','pool']

  html = []
  html.append("<br><br><table bgcolor=#F9F9F9 border=1 cellspacing=0><tr>")
  html.append("<td>time</td>")
  for attr in attrs:
    html.append("<td>")
    html.append(attr)
    html.append("</td>")
  html.append("</tr>")

  responseList = do_query(query, from_time, to_time)
  for response in responseList:
    if response.timeSeries:
      for ts in response.timeSeries:
        metadata = ts.metadata
        for data in ts.data:
          line = []
          if metadata.attributes:
            line.append("<tr>")
            line.append("<td>")
            line.append(utc2local(data.timestamp).strftime("%m-%d %H:%M:%S"))
            line.append("</td>")
            for attr in attrs:
              line.append("<td>")
              if metadata.attributes.has_key(attr):
                attrVal = metadata.attributes[attr]
                # 自动转换时长单位
                if ('application_duration' == attr):
                  if(int((float)(attrVal)) > 60 * 60 * 1000):
                    attrVal = ('%.2f' % ((float)(attrVal) / 60 / 60 / 1000)) + "h" # 小时
                  elif (int((float)(attrVal)) > 60 * 1000):
                    attrVal = (str)(int((float)(attrVal)) / 60 / 1000) + "m" # 分
                  elif (int((float)(attrVal)) > 1000):
                    attrVal = (str)(int((float)(attrVal)) / 1000)  + "s"# 秒
                if ('mb_millis' == attr):
                  if ((float)(attrVal) > 8 * 1024 * 1024 * 1024):
                    attrVal = ('%.2f' % ((float)(attrVal) / 8 / 1024 / 1024 / 1024)) + "G"
                  elif ((float)(attrVal) > 8 * 1024 * 1024):
                    attrVal = ('%.2f' % ((float)(attrVal) / 8 / 1024 / 1024)) + "M"
                  elif ((float)(attrVal) > 8 * 1024):
                    attrVal = ('%.2f' % ((float)(attrVal) / 8 / 1024)) + "K"
                if ('hdfs_bytes_read' == attr):
                  if ((float)(attrVal) > 1024 * 1024 * 1024):
                    attrVal = ('%.2f' % ((float)(attrVal) / 1024 / 1024 / 1024)) + "G"
                  elif ((float)(attrVal) > 1024 * 1024):
                    attrVal = ('%.2f' % ((float)(attrVal) / 1024 / 1024)) + "M"
                  elif ((float)(attrVal) > 1024):
                    attrVal = ('%.2f' % ((float)(attrVal) / 1024)) + "K"
                line.append(attrVal)
              else:
                line.append(' ')
              line.append("</td>")
            line.append("</tr>")
            heapq.heappush(h,(data.value,line))  #根据时长进行堆排序，Push的格式为(duration,<tr><td>attr1<td>...td>attrN<td></tr>)
  top20 = sorted(h, reverse=True)[0:20]
  for item in top20:
    html += item.__getitem__(1)
  html.append("</table>")
  report = ''.join(html)
  return report

#获取文件系统总容量
def getDfsCapacity(query,from_time,to_time):
  dfscapacity = 0
  unit = None

  responseList = do_query(query, from_time, to_time)
  for response in responseList:
    if response.timeSeries:
      for ts in response.timeSeries:
        for data in ts.data:
          dfscapacity = data.value
  return dfscapacity

def querySmallFiles(ip,user,password,command):
  html = []
  html.append("<br><br><table bgcolor=#F9F9F9 border=1 cellspacing=0>")

  client = ssh.SSHClient()
  client.set_missing_host_key_policy(ssh.AutoAddPolicy())
  client.connect(ip, port=22, username=user, password=password)
  stdin, stdout, stderr = client.exec_command(command)
  out = stdout.read()
  rows = out.split("\n")
  for row in rows:
    if (row.endswith('+') == False):
      cols = row.split("|")
      html.append("<tr>")
      for col in cols:
        if((col != ',') and (col != '')):
          html.append("<td>")
          html.append(col)
          html.append("</td>")
      html.append("</tr>")
  html.append("</table>")
  report = ''.join(html)
  return report

def queryFileIncreInfo(ip,user,password,command):
  timeList = []
  valfilesList = []
  valsizeList = []
  client = ssh.SSHClient()
  client.set_missing_host_key_policy(ssh.AutoAddPolicy())
  client.connect(ip, port=22, username=user, password=password)
  stdin, stdout, stderr = client.exec_command(command)
  out = stdout.read()
  rows = out.split("\n")
  for row in rows[3::]:
    if (row.endswith('+') == False):
      cols = row.split("|")
      if(len(cols) > 3):
        timeList.append(cols[1])
        valsizeList.append(float(cols[2]))
        valfilesList.append(float(cols[3]))

  line_chart6 = pygal.HorizontalBar(width=650, height=800)
  line_chart6.x_labels = timeList
  line_chart6.add('File Count', valsizeList)
  line_chart6.render_to_png('num_of_files.png')

  line_chart7 = pygal.HorizontalBar(width=650, height=800)
  line_chart7.x_labels = timeList
  line_chart7.add('Total size(G)', valfilesList)
  line_chart7.render_to_png('total_size_gb.png')


def main(argv):
  now = datetime.datetime.now()
  one_Hour_Ago = now - datetime.timedelta(hours=1)  # 前一小时
  one_Day_Ago = now - datetime.timedelta(days=1)# 前一天
  one_Week_Ago = now - datetime.timedelta(weeks=1)# 前一周
  one_Month_Ago = now - datetime.timedelta(days=30)# 前一月
  one_Quarter_Ago = now - datetime.timedelta(days=90)  # 前一季度
  two_Quarter_Ago = now - datetime.timedelta(days=180)  # 前两个季度

  lastThursday = utils.getDate.get_lastThursday(now) #上个周四的23:59:59
  lastFriday = utils.getDate.get_lastFriday(now) #最近周五的00:00:00
  lastmonth_to = utils.getDate.get_lastmonth_to(now)  # 上个月最后一天23:59:59

  #获取DFS信息
  dfs_capacity = getDfsCapacity("select dfs_capacity where  entityName=hdfs:nn-idc",None,None)
  dfs_capacity_used = getDfsCapacity("select dfs_capacity_used where  entityName=hdfs:nn-idc", None, None)
  dfs_capacity_used_non_hdfs = getDfsCapacity("select dfs_capacity_used_non_hdfs  where  entityName=hdfs:nn-idc", None, None)
  dfsRemaining = dfs_capacity - dfs_capacity_used - dfs_capacity_used_non_hdfs

  #群集CPU利用率-日报
  fileCPU = getReportChart("SELECT cpu_percent_across_hosts WHERE category = CLUSTER",
                           one_Day_Ago, now, CAPTIONCPU, filenameCPU,Granularity.RAW,'HOURLY', True)
  #群集内存使用率-日报
  fileMEM = getReportChart("SELECT 100 * total_physical_memory_used_across_hosts/total_physical_memory_total_across_hosts WHERE category=CLUSTER",
                           one_Day_Ago, now, CAPTIONMEM,filenameMEM, Granularity.RAW,'HOURLY', True)
  #群集网络传输量-日报
  fileNET = getReportChart("select total_bytes_transmit_rate_across_network_interfaces where category = CLUSTER",
                           one_Day_Ago, now, CAPTIONNET,filenameNET, Granularity.RAW,'HOURLY', True)
  #群集DFS使用量-周环比
  fileHDFSWeek = getHDFSWeekHistory("select dfs_capacity_used where  entityName=hdfs:nn-idc", two_Quarter_Ago, now,
                                    'Hadoop Cluster HDFS Report', Granularity.DAILY,'DAILY', True, dfs_capacity, dfsRemaining)
  #群集DFS使用量-月环比
  fileHDFSMonth = getHDFSMonthHistory("select dfs_capacity_used where  entityName=hdfs:nn-idc", two_Quarter_Ago, lastFriday,
                                    'Hadoop Cluster HDFS Report', Granularity.DAILY, 'WEEKLY', True)
  #群集DFS使用量-季度环比
  fileHDFSQuarter = getHDFSQtrHistory("select dfs_capacity_used where  entityName=hdfs:nn-idc", two_Quarter_Ago, lastFriday,
                                    'Hadoop Cluster HDFS Report', Granularity.DAILY, 'WEEKLY', True)

  picImpalaJobSummary = getImpalaJobSummary(one_Day_Ago, now)
  #IMPALA-运行时间超过5分钟的任务-日报
  impalaTop20 = getImpalaTop20("select query_duration from IMPALA_QUERIES where service_name = impala and query_duration >= 300000.0",
                               one_Day_Ago, now, "Impala Top 20",Granularity.RAW)

  picHiveJobSummary = getHiveJobSummary(one_Day_Ago, now)
  #Hive-运行时间超过30分钟的任务-日报
  hiveTop20 = getHive20(
    "select application_duration from YARN_APPLICATIONS where service_name = \"yarn\" and hive_query_id RLIKE \".*\" and application_duration >= 90000.0 ",
    one_Day_Ago, now, "Hive Top 20", Granularity.RAW)

  pwd = os.getcwd()
  picList = [pwd + "//" + 'hdfsweek.png',pwd + "//" + 'hdfsmonth.png',pwd + "//" + 'hdfsquarter.png',pwd + "//" + fileCPU,pwd + "//" +  fileMEM,\
             pwd + "//" + fileNET,pwd + "//" +  'num_of_files.png',pwd + "//" + 'total_size_gb.png',pwd + "//" + picImpalaJobSummary,pwd + "//" + picHiveJobSummary]

  mail_msg = "<h1>成都综合生产集群报告</h1>"
  mail_msg += "文件系统概况：<br/>" + "总容量：" + "%.1f" % (dfs_capacity / 1024 / 1024 / 1024 / 1024 ) + "T" \
              + "(已用HDFS容量：" + "%.1f" % (dfs_capacity_used / 1024 / 1024 / 1024 / 1024 ) + "T"\
              + "，已用非HDFS容量：" + "%.1f" % (dfs_capacity_used_non_hdfs  / 1024 / 1024 / 1024 / 1024 ) + "T" \
              + "，剩余容量：" + "%.1f" % (dfsRemaining  / 1024 / 1024 / 1024 / 1024 ) + "T" \
              + "，使用率：" + "%.1f"% ((1 - dfsRemaining / dfs_capacity) * 100) + "%)"
  mail_msg += "<br/>NameNode:2个,Datanode：30个<br/>"
  mail_msg += fileHDFSWeek + fileHDFSMonth + fileHDFSQuarter

  cmd = "impala-shell -i 10.214.128.11:21000 -l --auth_creds_ok_in_clear -u jiangshouzhuang --ldap_password_cmd=\"printf jiangshouzhuang\" \
        -q \"select to_date(t.day),t.num_of_files,t.total_size_gb \
        from ( \
            select trunc(modification_time,'DD') day,count(1) num_of_files, round(sum(filesize)/1024/1024/1024,2) total_size_gb \
            from idc_infrastructure_db.hdfs_meta where trunc(modification_time,'DD') is not null \
            group by trunc(modification_time,'DD') \
            order by trunc(modification_time,'DD') desc limit 30 \
        )t \
        order by t.day ;\" "
  queryFileIncreInfo("10.213.128.86",'yuanbowen1','Admin95594',cmd)
  mail_msg += "<br><br>每日文件增长数和大小<div><img src=cid:id6" + "><img src=cid:id7" + "></div>"

  mail_msg += "<br><br><br>群集CPU使用情况<p><img src=cid:id3" + "></p><br>"
  mail_msg += "<br><br>成都综合生产集群内存使用情况<p><img src=cid:id4" + "></p>"
  mail_msg += "<br><br>成都综合生产集群网络使用情况<p><img src=cid:id5" + "></p>"

  smallFiles = querySmallFiles("10.213.128.86", 'yuanbowen1', 'Admin95594',
                               "impala-shell -i 10.214.128.11:21000 -l --auth_creds_ok_in_clear -u jiangshouzhuang --ldap_password_cmd=\"printf jiangshouzhuang\" -q \"select db_name,tbl_name,tbl_owner,support_person,table_location,storage_format,file_size_type,small_files_count from idc_infrastructure_db.hdfs_small_files_result order by small_files_count desc limit 20\";")
  mail_msg += "<br><br>Top20小文件数"
  mail_msg += smallFiles

  mail_msg += "<br>IMPALA-任务执行时长统计<p><img src=cid:id8 style=\"vertical-align:middle;\"" + "></p>"
  mail_msg += "<br>IMPALA-运行时间超过5分钟的任务"
  if (impalaTop20.count("</tr>") > 1):
    mail_msg += impalaTop20
  else:
    mail_msg += "<br>没有超时任务，运行正常"

  mail_msg += "<br>Hive-任务执行时长统计<p><img src=cid:id9 style=\"vertical-align:middle;\"" + "></p>"
  mail_msg += "<br>Hive-运行时间超过15分钟的任务"
  if (hiveTop20.count("</tr>") > 1):
    mail_msg += hiveTop20
  else:
    mail_msg += "<br>没有超时任务，运行正常"

  # print mail_msg
  sendmail(FROM, TO, SUBJECT, mail_msg, picList)
  for pic in picList:
    os.remove(pic)

if __name__ == '__main__':
  sys.exit(main(sys.argv))
