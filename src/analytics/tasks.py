from __future__ import absolute_import, unicode_literals
from celery import shared_task, current_task


from django.conf import settings
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import sqlalchemy
from tkinter import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
#import matplotlib.backends.backend_pdf
from django.conf import settings
colrs = {0 :"#3366CC", 1 :"#8B0707", 2 :"#FF9900", 3 :"#109618", 4 : "#3B3EAC", 5 :"#3B3EAC", 6 :"#0099C6", 7 :"#DD4477", 8 :"#66AA00", 9 :"#B82E2E", 10 :"#316395", 11 :"#994499", 12 :"#22AA99", 13 :"#AAAA11", 14 :"#DC3912", 15 :"#E67300", 16 :"#6633CC", 17 :"#329262", 18 :"#5574A6", 19 :"#990099"}


#####
import pandas as pd
import numpy as np

########define DATABASE CONST#######################################################
user = settings.DATABASES['default']['USER']
password = settings.DATABASES['default']['PASSWORD']
database_name = settings.DATABASES['default']['NAME']
database_url = 'postgresql://{user}:{password}@localhost:5432/{database_name}'.format(user=user, password=password, database_name=database_name,)
####################################################################################

@shared_task
def load_to_database(path_to_file, keytab):
	try:
		df = pd.read_csv(path_to_file)
	except:
		print("Error: can't read csv")
		return 0

	########################
	#####DATABASE CONST#####
	########################
	engine = create_engine(database_url, echo=False)
	df.to_sql(keytab, con=engine, if_exists='replace', index=False)
	return 1


@shared_task
def calc(keytab, y_col):
	########################
	#####DATABASE CONST#####
	########################
	engine = create_engine(database_url, echo=False)
	df = pd.read_sql(keytab, con=engine)

	length=len(df.columns)

	y_col=y_col-1 #chng frmt :)
	#check and filters size of y_col
	if (y_col>=length):
		y_col=(length-1)
	elif (y_col<0):
		y_col=0

	#cut xy and insert to last
	def cut_insert(df, xy):
		label= df.columns[xy]
		values= df[df.columns[xy]]
		df=df.drop(df.columns[xy], axis=1)
		df.insert(len(df.columns), label, values)
		return df

	df=cut_insert(df, y_col) #rearrange df
	print("---------------------INS WAS OK-------------------")

	##drop the last col to get line of labels for X
	def get_cols_x(df):
		dfx=df.drop(df.columns[len(df.columns)-1], axis=1)
		return [n for n in dfx.columns]
	X=df[get_cols_x(df)].values

	## to get labels for Y drop all cols, except last
	def get_cols_y(df):
		return df.columns[len(df.columns)-1]

	Y=df[[get_cols_y(df)]].values

	print("---------------------MANIP WAS OK-------------------")
	####main calcs
	try:
		meanx, stds = np.mean(X, axis=0), np.std(X, axis=0)
		meany = np.mean(Y, axis=0)
		print(meanx)
		print(meany)
		print([l for l in df.columns])
		Xgraph=X
		X = (X-meanx)/stds
		X = np.hstack([np.ones((X.shape[0], 1)), X])
		norm_eq_weights= np.dot(np.linalg.pinv(X), Y)
		linear_prediction = np.dot(X,norm_eq_weights)
		mserror = sum(((linear_prediction-Y)**2))/Y.shape[0]
	except:
		print("some error occured")
		return 0
	print("---------------------CALC WAS OK-------------------")

	###################################################### 
	#print(settings.BASE_DIR+"/static/pics/"+keytab+".jpg")

	


	xlin=np.arange(start=0, stop=Y.max(), step=1) 
	acm = np.array([]) 
	print('STEP01')

	for x in xlin:
		x=[(x*w) for w in norm_eq_weights if w!=norm_eq_weights[0]]
		x=np.asarray(x)
		x=x.sum()
		acm = np.append(acm, (x+norm_eq_weights[0])/meany*3) 
	print('STEP02')


	fig=plt.figure()
	[(plt.scatter(Xgraph[:,n], Y, 10, colrs[n], 'o', alpha=0.5, label='data')) for n in range (len(Xgraph[0]))]
	print('STEP03')
	
	plt.plot(xlin, acm, color="red", alpha=1, label='data')
	print('STEP04')
	print(settings.BASE_DIR+"/static/pics/"+keytab+".jpg")
	
	plt.savefig(settings.BASE_DIR+"/static/pics/"+keytab+".jpg")
	#print(settings.BASE_DIR+"/static/pics/"+keytab+".png")
	#print(settings.STATIC_ROOT+"/pics/"+keytab+".png")

	#plt.savefig(settings.BASE_DIR+"/static/pics/"+keytab+".jpg", bbox_inches='tight')
	#pdf = matplotlib.backends.backend_pdf.PdfPages(settings.BASE_DIR+"/static/pics/"+keytab+".jpg")
	#plt.savefig(settings.STATIC_ROOT+"/pics/"+keytab+".png")
	######################################################

	#compile data
	str01=str(df.columns[len(df.columns)-1])
	print(str01)
	str02 = map(float, [x for x in norm_eq_weights])
	str03=float(mserror)
	str04=(y_col+1)
	str05= map(float, [x for x in meanx])
	str06=map(float, [x for x in meany])
	print("---------------------compile data OK-------------------")
	return [str01, [x for x in str02], str03, str04, [x for x in str05], [x for x in str06], [l for l in df.columns]]


@shared_task
def delete_from_database(keytab):
	########################
	#####DATABASE CONST#####
	########################
	engine = create_engine(database_url, echo=False)
	connection = engine.raw_connection()
	cursor = connection.cursor()
	try:
		command = "DROP TABLE \"{}\";".format(keytab)
		cursor.execute(command)
		connection.commit()
		txt = "DELETED SUCCESFULLY!"
	except:
		txt = "NOT DELETED!"
		pass

	cursor.close()

	return txt

@shared_task
def read_from_database(keytab):

	########################
	#####DATABASE CONST#####
	########################
	engine = create_engine(database_url, echo=False)
	df = pd.read_sql(keytab, con=engine)
	txt=df.to_html()

	return txt

