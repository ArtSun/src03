from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.template import loader
from django.views.decorators.csrf import csrf_protect, csrf_exempt, requires_csrf_token
#from django.views.decorators.cache import cache_page


# Create your views here.
from .models import Tabl, Weight
from .forms import TablLoadForm, TablSnapForm, TablChngForm
from .tasks import calc
from celery.result import AsyncResult
import celery
import json
from celery.task.control import revoke

#@cache_page(60 * 15)
#@csrf_protect
#@requires_csrf_token
@csrf_exempt
def analytics_load(request):
	queryset = Tabl.objects.all().order_by('timestamp').reverse()[:12]
	if request.method == 'POST':
		form = TablLoadForm(request.POST or None, request.FILES or None)
		if form.is_valid() and request.recaptcha_is_valid:
			instance=form.save(commit=False)
			instance.set_name_and_keytab()			
			if instance.load_to()==0:
				instance.delete()
				messages.error(request, "Error! Table isn't loaded, please check data in the file")
				queryset = Tabl.objects.order_by('timestamp').reverse()[:3]
				form = TablLoadForm()
				context = {
					"form" : form,
					"object_list" : queryset,
				}
				return render(request, "analytics_load_form.html", context)
			messages.success(request, "Succesfully added")
			return HttpResponseRedirect(instance.get_snap_url())
		elif form.errors:
			form = TablLoadForm()
			context = {
				"form" : form,
				"object_list" : queryset,
			}
			messages.error(request, "Error! Table isn't loaded, please check data in the file")
			return render(request, "analytics_load_form.html", context)
		else:
			form = TablLoadForm()
			context = {
				"form" : form,
				"object_list" : queryset,
			}
			return render(request, "analytics_load_form.html", context)
			#pass
	else:
		form = TablLoadForm()
		context = {
		"form" : form,
		"object_list" : queryset,
		}
		return render(request, "analytics_load_form.html", context)

#@cache_page(60 * 15)

#@csrf_protect
@csrf_exempt
def analytics_snap(request, key=None):
	instance = get_object_or_404(Tabl, keytab=key)
	instance.set_rest() #read from database; set y_col; content_slice; content_full;
	form = TablSnapForm(request.POST or None, instance=instance)
	formChng = TablChngForm(request.POST or None, instance=instance)
	if formChng.is_valid():
		instance=formChng.save(commit=False)
		instance.save()
		instance.change_tabl()
		return HttpResponseRedirect(instance.get_snap_url())
	if form.is_valid():
		instance=form.save(commit=False)
		instance.save()
		job = calc.delay(instance.keytab, instance.y_col)
		replace="/"+str(instance.keytab)+"/result/"+"?id="+str(job.id)
		context = {
			#'url': "/analytics/"+str(instance.keytab)+'/wait/',
			'url':"/"+str(instance.keytab)+'/wait/',
			'task_id':job.id,
			'replace':replace,
			'instance':instance,
			}
		return render(request,"wait_form.html",context)

	if 'showfull' in request.GET.keys() and request.GET['showfull']:
		is_full=True
	else:
		is_full=False
	context = {
		"instance" : instance,
		"form" : form,
		"formChng" : formChng,
		"full_cont" : is_full,
	}
	return render(request, "analytics_snap_form.html", context)

#@cache_page(60 * 15)
#@csrf_protect
def reld(request, key=None):
	instance = get_object_or_404(Tabl, keytab=key)
	print("PATH: ", instance.tfile.path, "KEYTAB: ", instance.keytab)
	try:
		instance.load_to()
	except:
		pass
	if instance.load_to()==0:
		messages.error(request, "Error! Some issues with the table")
		HttpResponseRedirect(instance.get_absolute_url())
	instance.set_rest()
	return HttpResponseRedirect(instance.get_snap_url())

#@cache_page(60 * 15)
#@csrf_protect
def wait(request, key=None):
	print("REQUEST IN WAIT:", request)
	instance = get_object_or_404(Tabl, keytab=key)
	if request.is_ajax():
		print("AJAX! REQUEST")
		if 'task_id' in request.POST.keys() and request.POST['task_id']:
			task_id = request.POST['task_id']
			task = AsyncResult(task_id)
			try:
				print("TASK RESULT: ", task.result)
				print("TASK STATE: ", task.state)
			except:
				pass
			data = task.result or task.state
			if (task.state=="SUCCESS" and task.result!=0 and task.ready()):
				print("IN SUCCESS", task.state)
				data="ok"
				weights = instance.weight_set.all()
				weights.delete() #del prev weights
				weights = task.result[1]
				instance.name_y_col=task.result[0]
				meanx = task.result[4]
				meany = task.result[5]
				labls = task.result[6]
				instance.make_weights(weights, meanx, meany, labls)
				instance.ms_error = task.result[2]
				instance.y_col = task.result[3]
				instance.save()
				json_data = json.dumps(data)
				return HttpResponse(json_data, content_type='application/json')
				#return HttpResponseRedirect(instance.get_result_url()+"?id="+str(task_id))
			elif task.state=="PENDING":
				#data={"task_id": task_id}
				data=0
				json_data = json.dumps(data)
				return HttpResponse(json_data, content_type='application/json')
			else:
				print("PROBLEMS WITH DATA", task.state)
				#instance.delete()
				data=-1
				json_data = json.dumps(data)
				return HttpResponse(json_data, content_type='application/json')
		else:
			data=0
			json_data = json.dumps(data)
			print('No task_id in the request')
			return HttpResponse(json_data, content_type='application/json')
	else:
		print("REQUEST NOT AJAX!")
		data=0
		json_data = json.dumps(data)
		return HttpResponse(json_data, content_type='application/json')



def result(request, key=None):
	print(request)
	print(request.GET.keys())
	#print(request.GET['id'])
	print("here we are")
	instance = get_object_or_404(Tabl, keytab=key)
	if 'id' in request.GET.keys() and request.GET['id']:
		job_id=request.GET['id']
		print(job_id)
		print("NEW!!!!", AsyncResult(job_id).ready())
		f = open('text.txt', 'w')
		f.write(str(AsyncResult(job_id).ready()))
		f.close()
		#instance.name_y_col = AsyncResult(job_id).result[0]
		
		print(instance.name_y_col)
		#weights = instance.weight_set.all()
		#weights.delete() #del prev weights
		
		#weights = AsyncResult(job_id).result[1]
		#meanx = AsyncResult(job_id).result[4]
		#meany = AsyncResult(job_id).result[5]
		#labls = AsyncResult(job_id).result[6]
		#instance.make_weights(weights, meanx, meany, labls)
		print("actually here")


	print("and there")
	weights = [x for x in instance.weight_set.all()]
	context = {
		"instance": instance,
		"weights" : weights,
		}
	template = loader.get_template('analytics_result_form.html')
	return HttpResponse(template.render(context, request))

	
		
