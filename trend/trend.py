import numpy as np
import matplotlib.pyplot as plt



class determine_trend():
	def __init__(self,array,name):
		self.array = array
		self.threshold = 0.65
		self.size = len(array)
		print(array)
		plt.plot(range(self.size),array,label=name)
		plt.legend(loc='best')
		self.determine_trend()

	def determine_trend(self):
		if len(self.array)<2:
			print("Not enough datapoints")
			return
		
		upward=False if self.array[1]<self.array[0] else True
		prev_point= (0,self.array[0])
		lows=[prev_point]
		highs=[prev_point]
		for idx,point in enumerate(self.array[1:],start=1):
			if point > prev_point[1] and not upward:
				lows.append(prev_point)
				upward=True
			elif point < prev_point[1] and upward:
				highs.append(prev_point)
				upward=False
			prev_point=(idx,point)
		if upward:
			highs.append(prev_point)
		else:
			lows.append(prev_point)
		print(lows)
		print(highs)
		uptrend=downtrend=0
		init_low=lows[0][1]
		init_high=highs[0][1]
		for idx,low in lows:
			if low > init_low:
				uptrend+=1.0
			elif low < init_low:
				downtrend+=1.0
			init_low=low
		for idx,high in highs:
			if high > init_high:
				uptrend+=1.0
			elif high < init_high:
				downtrend+=1.0
			init_high=high
		trend_total=uptrend+downtrend
		print(downtrend,uptrend,trend_total)
		if uptrend/trend_total > self.threshold:
			result='uptrend'
		elif downtrend/trend_total > self.threshold:
			result='downtrend'
		else:
			result='sideways'
		print("Analysis: Trend is %s"%(result))
		plt.title(result)
		plt.show()
			
				
