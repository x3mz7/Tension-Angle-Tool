#from ctypes import alignment
import os #,  sys
import pandas as pd  # pip install pandas
import plotly.express as px  # pip install plotly-express
#from openpyxl import *
from datetime import datetime
from time import time, sleep
#import base64  # Standard Python Module
import OrcFxAPI as OF, numpy as np, glob, tkinter as tk
from tkinter import filedialog
import streamlit as st
#import streamlit.components.v1 as stc
from streamlit_option_menu import option_menu
from st_aggrid import AgGrid, GridUpdateMode  # , DataReturnMode, JsCode
from st_aggrid.grid_options_builder import GridOptionsBuilder
import warnings
from multiprocessing.pool import ThreadPool
#from threading import active_count
#from multiprocessing import Pool
#from itertools import count
#from io import StringIO, BytesIO  # Standard Python Module
warnings.simplefilter(action='ignore', category=FutureWarning)
import pandas as pd  # pip install pandas
import TA_database as db  # local import
#from streamlit.runtime.scriptrunner import add_script_run_ctx

st.set_page_config(page_title='T-A Plotter', page_icon=':chart_with_upwards_trend:')
#st.title('Tension-Angle Plotter 📈')

# TOOL TIP Definition:
LineEnd_tooltip = 'Set Line End(s) to End A or End B. Note this will reset the Table below.'

# read button style defined in css file stored in app directory
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
local_css("style.css")

if 'simFileLocationCopy' not in st.session_state:
    st.session_state.simFileLocationCopy=""
    st.session_state['simLocation'] = ""
    st.session_state['lineEnd'] = "End A"
    st.session_state['t_a_Pack']={}  # will hold data as pandas df
    st.session_state['t_a_Pack_noDF']={}  # will hold raw dicts to be sent to db
    st.session_state['theLines']=[]
    st.session_state['rev_t_a_Pack']={}  # will hold reviewed data as pandas df
    st.session_state['rev_t_a_Pack_noDF']={}  # will hold reviewed raw dicts from db
    st.session_state['rev_theLines']=[]  
    st.session_state.saveDayta=False
    st.session_state.confirmSave=0
    st.session_state.blankErrorCount=0
    st.session_state.theFormattedTytl=''  # this would change based on whether the T-A plot is a new result or saved data
    st.session_state.threadCount=os.cpu_count()+1  # used to populate no of threads selectBox
    st.session_state.knownPeriods=[]
    st.session_state['tStart']=0.0
    st.session_state['tEnd']=0.0
    st.session_state.disabled = False  # state of button widget
    st.session_state.startProcess=""  #holds the status of T-A extraction process
    st.session_state.abortTask=False  #abort process Flag

st.session_state.selected=option_menu(
                menu_title="📈 Tension-Angle Plotter",
                options=["Home", "T-A Plots", "Review"],
                icons=["house", "list-stars", "book"],  # https://www.webfx.com/tools/emoji-cheat-sheet/
                menu_icon="chart uptrend",
                default_index=0,
                orientation="horizontal",
                styles={
                    "container": {"padding": "0!important", "background-color": "#464e5f"},
                    "icon": {"color": "cyan", "font-size": "25px"}, 
                    "nav-link": {"font-size": "25px", "text-align": "center", "margin":"0px", "--hover-color": "#3F96A7"},
                    "nav-link-selected": {"background-color": "brown"},
                }
                )

# HIDE THE DEFAULT STREAMLIT MENU & FOOTER
hide_menu_style = """
        <style>
        #MainMenu {visibility: hidden; }
        footer {visibility: hidden; }
        </style>
        """
st.markdown(hide_menu_style, unsafe_allow_html=True)
st.write('---')
simFileLocation=""; temp = []

def getDirPath():
    # Set up tkinter
    root = tk.Tk()
    root.withdraw()
    # Make folder picker dialog appear on top of other windows
    root.wm_attributes('-topmost', 1)
    st.session_state.simFileLocationCopy = filedialog.askdirectory(master=root)
    # st.session_state['simLocation'] = filedialog.askdirectory(master=root)

def worker(workPack):
    global temp
    #if not(st.session_state.abortTask):
    FileName, riser, end, duration = workPack
    loadCase_Hdr='Load Case'; time_Hdr='Time (s)'
    tension_Hdr = 'Tension (' + tension_unit + ')'; angle_Hdr = 'Angle (' + angle_unit + ')'
    model = OF.Model(FileName)
    Riser = model[riser]
    end="OF.oe"+end.replace(' ','')
    t= model.SampleTimes(duration)
    T = Riser.TimeHistory('Effective tension', duration, eval(end))  # get effective tension / end force
    A = Riser.TimeHistory('Ez angle', duration, eval(end))  # get Ez-angle
    for d in range(len(T)):
        temp[-1][loadCase_Hdr].append(os.path.basename(FileName))
        temp[-1][time_Hdr].append(t[d])
        temp[-1][tension_Hdr].append(T[d])
        temp[-1][angle_Hdr].append(A[d])
    return ""  #"done "+str(riser)+" in "+os.path.basename(FileName)
    

def terminator_T1000():
    ## Check for active processes and kill them    
    children = ThreadPool.active_children() 
    st.write("Currently Active Children of Main Process Count : {}".format(children))
    for child_process in children:
        if child_process.is_alive():
            child_process.terminate()
            st.write("Terminating Process : {}".format(child_process.name))

def getTAdataNow(simFileLocation, RISERS, eNds, tension_unit, angle_unit):
    global Duration; global iNfoStr; global temp  #; global t_a_Pack
    # ; sleep(0.5)  # tempDisp=st.empty; 
    iD_Hdr='ID'; loadCase_Hdr='Load Case'; time_Hdr='Time (s)'
    tension_Hdr = 'Tension (' + tension_unit + ')'; angle_Hdr = 'Angle (' + angle_unit + ')'
    
    temp=[]; taskCompltd=0; k=0  # count the number of load cases to process
    #tempDisp.empty()
    ## perform detailed validation if period selected is "Specified period" 
    if st.session_state['Duration']=='Specified period':
        try:
            if st.session_state['tStart']!='~': float(st.session_state['tStart'])
            if st.session_state['tEnd']!='~': float(st.session_state['tEnd'])
        except:
            tempDisp.warning("Invalid specified period given.", icon="❌")
            sleep(3);tempDisp.empty()
            return "processAborted!"
        if st.session_state['tStart']=='~':st.session_state['tStart']=float(simStart)
        if st.session_state['tEnd']=='~':st.session_state['tEnd']=float(simEnd)
        if float(st.session_state['tStart'])<simStart:st.session_state['tStart']=float(simStart)
        if float(st.session_state['tEnd'])>simEnd:st.session_state['tEnd']=float(simEnd)
        if float(st.session_state['tStart'])>float(st.session_state['tEnd']):
            tempDisp.empty(); tempDisp.warning("Specified period – \"From\" time cannot be greater than \"To\" time.", icon="❌")
            sleep(3);tempDisp.empty()
            return "processAborted!"

    st.sidebar.empty()
    finalStatus=st.sidebar.empty()
    execTimeFrame=st.sidebar.empty()
    sepFrame=st.sidebar.container()
    #st.sidebar.write('na wa...')
    #finalStatus.success('The process completed successfully!', icon="✅")
    #try:
    Durayshun={'Specified period':OF.SpecifiedPeriod(float(st.session_state['tStart']), float(st.session_state['tEnd'])), 'Latest wave':OF.pnLatestWave, 'Whole simulation':OF.pnWholeSimulation, 'Build-up':0}
    #except:
    #    pass
    for mP in modelPeriods:
        if 'Stage 'in mP: Durayshun[mP]=eval(mP.split(' ')[1])
    duration=Durayshun[st.session_state['Duration']]

    st.sidebar.write("Starting..."); st.sidebar.write('Preparing file(s). Please wait...')
    for FileName in glob.glob(simFileLocation + '\\' + '*.sim'):
        k += 1
    st.sidebar.write('Number of Risers to Analyse: ', len(RISERS))
    st.sidebar.write('Number of Files to Post-Process: ', k)
    st.sidebar.write('Starting with ', st.session_state.selectedThreads, ' Thread(s).')
    taskCount=k*len(RISERS); startTime = time()
    for r, riser in enumerate(RISERS):
        #temp.append({iD_Hdr:[], loadCase_Hdr:[], time_Hdr:[], tension_Hdr:[], angle_Hdr:[]})
        temp.append({loadCase_Hdr:[], time_Hdr:[], tension_Hdr:[], angle_Hdr:[]})
        st.sidebar.write('Getting data for', riser); LoadCasePack=[] #; idd=0

        for simFly in glob.glob(simFileLocation + '\\' + '*.sim'):
            LoadCasePack.append((simFly, riser, eNds[r], duration))
            #st.sidebar.write(LoadCasePack[-1])
        #st.sidebar.write('files collated...')
        
        if st.session_state['selectedThreads']==1:
            for LoadCase in LoadCasePack:
                if st.session_state.abortTask:
                    return "processAborted!"
                result=worker(LoadCase)
                taskCompltd+=1; progBar.progress(int(round((taskCompltd/taskCount)*100)))
        else:
            with ThreadPool(st.session_state['selectedThreads']) as pool:
                #st.write(st.session_state.abortTask)
                for result in pool.imap_unordered(worker, LoadCasePack):
                    if st.session_state.abortTask:
                        st.write(st.session_state.abortTask)
                        st.write("Aborting...")
                        break
                    taskCompltd+=1; progBar.progress(int(round((taskCompltd/taskCount)*100)))
                if st.session_state.abortTask:
                    return "processAborted!"
                    
                
    for tmp in temp: tmp[iD_Hdr] = getattr(np.arange(1, len(tmp[tension_Hdr])+1), "tolist")()

    executionTime = round((time() - startTime), 0); unit='second(s)'
    if executionTime>59.5 and executionTime<3600.0:
        executionTime=round(executionTime/60.0,1); unit='minute(s)'
    if executionTime>=3600.0:
        executionTime=round(executionTime/3600.0,1); unit='hour(s)'
    execTimeFrame.write('Execution time: '+str(executionTime)+' '+unit+'.')
    sepFrame.write('---')

    st.session_state['t_a_Pack']={RISERS[i]: pd.DataFrame(temp[i]) for i in range(len(RISERS))}
    st.session_state['t_a_Pack_noDF']={RISERS[i]: temp[i] for i in range(len(RISERS))}
    st.sidebar.write('---')
    st.sidebar.info('Chart(s) are available in \"T-A Plots\" page.', icon="💡")
    finalStatus.success('The process completed successfully!', icon="✅")
    return "processCompleted!"

@st.cache
def get_df(id, line, lineEnd):
    return pd.DataFrame({'ID':id, 'Line Name':line, 'Line End':lineEnd})

@st.cache
def get_df2(colHdr, columnsOfExstingData):
    return pd.DataFrame({colHdr[i]:columnsOfExstingData[i] for i in range(len(colHdr))})

# def lineEndOptionChanged():
#     with simAddressFrame:
#         simFileLocation = st.text_input('Selected Folder', placeholder="Load Case Directory", value=st.session_state.simFileLocationCopy, label_visibility = "collapsed")

# st.set_page_config(page_title='T-A Plotter', page_icon=':chart_with_upwards_trend:')
# st.title('Tension-Angle Plotter 📈')

def invertState():
    st.session_state.disabled = not(st.session_state.disabled)
    if not(st.session_state.disabled):
        st.session_state.abortTask=True
        st.write(st.session_state.abortTask)

def resetProcessStatus():
    st.session_state.startProcess=""

def updatePeriodList(t):
    st.session_state.knownPeriods=t

def updateModelSettins():
    colDuration, specDur1, specDur2, colThread, colLineEnd = st.session_state.modelSettins.columns([1.0,0.5,0.5,1.0,0.5])
    if 'Latest wave' in st.session_state.knownPeriods:
        indX=1
    else:
        indX=3
    Duration=colDuration.selectbox("Period:", st.session_state.knownPeriods, on_change=resetProcessStatus, disabled=st.session_state.disabled, index=indX, key='Duration')
    if st.session_state['Duration']=="Specified period":
        specTimeStart=specDur1.text_input("From (s):", value="~", key='specTimeStart', disabled=st.session_state.disabled, label_visibility="visible")
        specTimeEnd=specDur2.text_input("To (s):", value="~", key='specTimeEnd', disabled=st.session_state.disabled, label_visibility="visible")
        st.session_state['tStart']=specTimeStart
        st.session_state['tEnd']=specTimeEnd
    selectedThreads=colThread.selectbox("Thread Count:", [t for t in range(1, st.session_state.threadCount)], on_change=resetProcessStatus, disabled=st.session_state.disabled, index=(st.session_state.threadCount)-2, key='selectedThreads')
    batchAllEnds=colLineEnd.radio("Line End:", options=['End A', 'End B'], help=LineEnd_tooltip, disabled=st.session_state.disabled, key='lineEnd')  # , on_change=lineEndOptionChanged)
    #st.session_state.startProcess=""

#nSub=1
if st.session_state.selected=="Home":
    #if not(st.session_state.disabled):
    st.session_state.simAddressFrame=""; st.session_state.modelSettins=""
    #def runInputSettings(refretsh):
    #global nSub; nSub+=1
    #topForm=st.container()
    #global simAddressFrame, modelSettins
    #if not(refretsh):
    subTytl, OFx_img, blNk=st.columns([10,1,2])  # st # topForm
    theFormattedTytl = '<p style="font-family:Arial; text-align: left; color:brown; font-weight: bold; font-style: italic; font-size: 25px;">'+"Load your OrcaFlex Simulation(s)"+'</p>'
    subTytl.markdown(theFormattedTytl, unsafe_allow_html=True)
    #subTytl.markdown('### Feed me with your OrcaFlex Simulation(s)')
    OFx_img.image('OrcaFlex-noBG+.png')
    #st.write("na wa!")
    st.session_state.selectFolderFrame=st.empty()
    colsSelectFolderFrame=st.session_state.selectFolderFrame.columns([3,3,3,3])
    
    #btnLoadCasesLocation=st.session_state.selectFolderFrame.button(label="Select Folder...", disabled=st.session_state.disabled, key=nSub) # st.button(label="Select Folder...") # topForm.form_submit_button(label="Select Folder...")
    btnLoadCasesLocation=colsSelectFolderFrame[0].button(label="Select Folder...", disabled=st.session_state.disabled)
    #if not(refretsh):
    txtFrame=st.empty()  # st # topForm
    st.session_state.modelSettins=st.container()  # st # topForm
    #lineListFrame=st.container()
    col1, col2 = txtFrame.columns([2.5,0.001])
    
    st.session_state.simAddressFrame=col1.empty()
    with st.session_state.simAddressFrame:
        simFileLocation = st.text_input('Selected Folder', placeholder="Load Case Directory", disabled=st.session_state.disabled, key='simLocation', label_visibility="collapsed")
        
    #if not(refretsh):
    st.write(
    """<style>
    [data-testid="stHorizontalBlock"] {
        align-items: center;
    }
    </style>
    """,
    unsafe_allow_html=True
    )

    if btnLoadCasesLocation:
        try:
            del grid_table; del gd
        except:
            pass
        getDirPath()
        simFileLocation=st.session_state.simFileLocationCopy

    #st.session_state['tStart']=0.0; st.session_state['tEnd']=0.0

    #if not(st.session_state.disabled): runInputSettings(False)

    with st.form("BorderFrame"):
        if st.session_state.simFileLocationCopy:
            with st.session_state.simAddressFrame:
                simFileLocation = st.text_input('Selected Folder', placeholder="Load Case Directory", value=st.session_state.simFileLocationCopy, label_visibility = "collapsed")
        lines=""; dll_err=""
        if simFileLocation:
            try:
                for FileName in glob.glob(simFileLocation + '\\' + '*.sim'):
                    sampleModel=OF.Model(FileName.replace("/","\\"))
                    lines=[obj.name for obj in sampleModel.objects if obj.type == OF.otLine]
                    tension_unit = sampleModel['General'].ForceUnits
                    angle_unit ='deg'
                    simStart=sampleModel['General'].StageStartTime[0]
                    simEnd=sampleModel['General'].StageEndTime[sampleModel['General'].StageCount-1]
                    modelPeriods=['Specified period', 'Whole simulation', 'Build-up']+['Stage '+str(p) for p in range(1, sampleModel['General'].StageCount)]
                    #try:
                    if sampleModel['Environment'].WaveHeight:
                        modelPeriods.insert(1, 'Latest wave')
                    #except:
                    #    pass
                    updatePeriodList(modelPeriods)
                    updateModelSettins()
                    break
            except OF.DLLError as dll_e:
                #st.warning(dll_e, icon="❌")
                dll_err="Unable to obtain an OrcaFlex Licence."
                st.warning("Unable to obtain an OrcaFlex Licence.", icon="❌")

            defaultLineEnd=[st.session_state['lineEnd'] for line in range(len(lines))]; whatEnd=['End A', 'End B']
            iD=[str(x+1) for x in range(len(lines))]
            line_DF=get_df(iD, lines, defaultLineEnd)
            if lines:
                gd = GridOptionsBuilder.from_dataframe(line_DF)
                gd.configure_pagination(enabled=True)
                #gd.configure_default_column(editable=False)  # groupable=True)
                gd.enableRangeSelection=True
                gd.configure_column('ID', headerCheckboxSelection=True)
                #gd.configure_column('Tension (kN)', type=["numericColumn","numberColumnFilter","customNumericFormat"], precision=1)
                #gd.configure_column('Angle (deg)', type=["numericColumn","numberColumnFilter","customNumericFormat"], precision=1)
                gd.configure_column('Line End', editable=True, cellEditor='agSelectCellEditor', cellEditorParams={'values': whatEnd})
                gd.configure_selection(selection_mode='multiple', use_checkbox=True)  # , pre_selected_rows=[i for i in range(len(lines))])  # all checkbox pre-selected
                st.write('**Select Line(s):**')
                gridoptions=gd.build()
                grid_table = AgGrid(line_DF,
                                    gridOptions=gridoptions,
                                    update_mode= GridUpdateMode.MODEL_CHANGED,  # SELECTION_CHANGED,
                                    fit_columns_on_grid_load=True,
                                    #data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                                    height = 400,
                                    allow_unsafe_jscode=True,
                                    enable_enterprise_modules = True,
                                    theme = 'alpine')

                sel_row = grid_table["selected_rows"]
        tempDisp=st.empty()
        baseFrame=st.columns([1.2,8,1.2])
        customized_button = st.markdown("""
        <style >
        .stDownloadButton, div.stButton {text-align:center}
        </style>""", unsafe_allow_html=True)
        getFormParams=baseFrame[0].form_submit_button("Start", on_click=invertState, disabled=st.session_state.disabled)  #, disabled=st.session_state.disabled)
        progBar=baseFrame[1].progress(0)
        abortProcess=baseFrame[2].form_submit_button("Abort", on_click=invertState, disabled=not(st.session_state.disabled))
        if getFormParams:
            #btnLoadCasesLocation=selectFolderFrame.button(label="Select Folder...", disabled=st.session_state.disabled)
            # if st.session_state.disabled:
            #     tempDisp.empty();tempDisp.info("Session running... please wait.", icon="💡")
            #     sleep(3); tempDisp.empty()
            # else:
            try:
                if not(sel_row):1/0  # check if line(s) have been selected
                st.session_state['theLines']=[]; theEnds=[]
                for struc in sel_row:
                    st.session_state['theLines'].append(struc['Line Name'])
                    theEnds.append(struc['Line End'])
                #st.session_state.disabled=True
                #runInputSettings(st.session_state.disabled)
                st.session_state.abortTask=False
                st.session_state.startProcess=getTAdataNow(simFileLocation,st.session_state['theLines'],theEnds,tension_unit,angle_unit)
                
                if st.session_state.startProcess=="processCompleted!":
                    st.session_state.theFormattedTytl = '<p style="font-family:Arial; text-align: left; color:brown; font-weight: bold; font-style: italic; font-size: 25px;">'+"View Results 👓"+'</p>'
                    tempDisp.empty();tempDisp.success('The process completed successfully!', icon="✅")
                    sleep(2);tempDisp.info('Chart(s) are available in \"T-A Plots\" page.', icon="💡")
                elif st.session_state.startProcess=="processAborted!":
                    tempDisp.empty();tempDisp.info('The process was aborted.', icon="💡")
                    sleep(2);tempDisp.empty()
                #runInputSettings(True)
            except:  # catch potential errors
                try:
                    if grid_table and not(sel_row):
                        tempDisp.empty();tempDisp.info("You must select one or more lines👆 to continue.", icon="❗")
                except:
                    if dll_err:
                        tempDisp.empty();tempDisp.info("Unable to obtain an OrcaFlex Licence.", icon="❌")
                    elif os.path.exists(simFileLocation):
                        tempDisp.empty();tempDisp.info("No OrcaFlex simulation(s) found in the selected folder.", icon="🧐")
                    else:
                        tempDisp.empty();tempDisp.info("You must select a folder containing OrcaFlex simulation files.", icon="❗")
                sleep(3); tempDisp.empty()

        if not(st.session_state.abortTask):
            try:
                if st.session_state.startProcess=="processCompleted!" and sel_row:
                    sleep(5)
                    tempDisp.success('The process completed successfully. Chart(s) are available in \"T-A Plots\" page.', icon="💡")
            except:
                pass
        else:  # st.session_state.abortTask:
            #sleep(5)
            tempDisp.info('The process was aborted.', icon="ℹ️")
    if st.session_state.disabled==True or st.session_state.abortTask:
        st.session_state.disabled=False
        st.experimental_rerun()

if st.session_state.selected=="T-A Plots":
    subTytl, img, blNk=st.columns([10,1,2])
    #theFormattedTytl = '<p style="font-family:Arial; text-align: left; color:brown; font-weight: bold; font-style: italic; font-size: 25px;">'+"View Results"+'</p>'
    subTytl.markdown(st.session_state.theFormattedTytl, unsafe_allow_html=True)
    def chartRequested():
        if st.session_state.selected=="T-A Plots":
            if st.session_state.thisResultName in st.session_state['theLines']:
                st.session_state.resultPair=theOptDef[st.session_state.thisResultOptn]
                with chartFrame:
                    #st.markdown('### '+st.session_state.thisResultName)
                    fig=px.scatter(st.session_state['t_a_Pack'][st.session_state.thisResultName],
                                    x=st.session_state['t_a_Pack'][st.session_state.thisResultName][st.session_state.resultPair[0]],
                                    y=st.session_state['t_a_Pack'][st.session_state.thisResultName][st.session_state.resultPair[1]],
                                    title=st.session_state.thisResultName+" "+st.session_state.thisResultOptn+" Plots"
                                )
                    fig
    
    def updateResultPair():
        if st.session_state.selected=="T-A Plots":
            if st.session_state['theLines'] and st.session_state.thisResultName in st.session_state['theLines']:
                st.session_state.resultPair=theOptDef[st.session_state.thisResultOptn]
                chartRequested()
                return

    def tableRequested():
        if st.session_state.selected=="T-A Plots":
            if st.session_state.thisResultName in st.session_state['theLines']:
                with tableFrame:
                    st.markdown('### '+st.session_state.thisResultName)
                    grid_table = AgGrid(st.session_state['t_a_Pack'][st.session_state.thisResultName],
                                        key=st.session_state.thisResultName+'_key',
                                        gridOptions=gridoptions,
                                        update_mode= GridUpdateMode.MODEL_CHANGED,  # SELECTION_CHANGED,
                                        fit_columns_on_grid_load=True,
                                        #data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                                        height = 400,
                                        allow_unsafe_jscode=True,
                                        enable_enterprise_modules = True,
                                        theme = 'alpine')
                st.session_state.saveDayta=True
    
    def saveThisSession(projName, projVersion, projClient, projComment):
        tempDisp=st.empty()
        if not(projName and projVersion and projClient):
            st.session_state.blankErrorCount+=1
            if st.session_state.blankErrorCount==2:
                st.warning("Fields marked with ✳️ are required. Data not saved.", icon="❌")
                st.session_state.blankErrorCount=0
            sleep(2); tempDisp.empty()
            return
        date_stamp=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        date_saved=date_stamp.split()[0]; time_saved=date_stamp.split()[1]
        sessionData=projName+" - "+projVersion+" - "+projClient+" - "+date_saved+" - "+time_saved
        sessionData=sessionData.strip().strip("-").strip()
        db.insert_session(sessionData, projName, projVersion, projClient, date_saved, time_saved, projComment, st.session_state['t_a_Pack_noDF'])
        tempDisp.success("Data saved!", icon="✔️")
        sleep(2); tempDisp.empty()

    st.session_state.resultPair=['Angle (deg)', 'Tension (kN)']
    availableResult=[]; resultName=[]
    with st.form("plotsFrame"):
        colResult, colOpt, colViewTable=st.columns([3,2,1])
        colViewTable.text("");colViewTable.text("")  # just padding with blank texts to push button down
        btnGo=colViewTable.form_submit_button("Plot!")
        #st.form_submit_button("click me")
        #if st.session_state['t_a_Pack']: resultName.append("Select Chart:")
        for p, pack in enumerate(st.session_state['t_a_Pack']):
            gd = GridOptionsBuilder.from_dataframe(st.session_state['t_a_Pack'][st.session_state['theLines'][p]])
            gd.configure_pagination(enabled=False)
            gd.configure_default_column(editable=False)  # groupable=True)
            gd.configure_column("ID", headerCheckboxSelection = False)
            #gd.configure_column('Line End', editable=True, cellEditor='agSelectCellEditor', cellEditorParams={'values': whatEnd})
            #gd.configure_selection(selection_mode='multiple', use_checkbox=True)  # , pre_selected_rows=[i for i in range(len(lines))])  # all checkbox pre-selected
            gridoptions=gd.build()
            availableResult.append(gd)
            resultName.append(st.session_state['theLines'][p])
        
        #thisResultName = colResult.selectbox("Selected Line", resultName, key="thisResultName", on_change=chartRequested, label_visibility="collapsed")
        thisResultName = colResult.selectbox("Select Line:", resultName, key="thisResultName")
        theOptDef={'Tension vs Angle': ['Angle (deg)', 'Tension (kN)'],
                    'Tension vs Time': ['Time (s)', 'Tension (kN)'],
                    'Angle vs Time': ['Time (s)', 'Angle (deg)']}
        theOptions=['Tension vs Angle', 'Tension vs Time', 'Angle vs Time']
        #if resultName: thisResultOptn = colOpt.selectbox("Select Plot:", theOptions, key="thisResultOptn", on_change=updateResultPair, label_visibility="collapsed")
        if st.session_state['t_a_Pack']: thisResultOptn = colOpt.selectbox("Select Plot:", theOptions, key="thisResultOptn")
        #if resultName: colViewTable.button("View Table", key="viewTable", on_click=tableRequested)
        ##and resultName in st.session_state['t_a_Pack']
        
        chartFrame=st.container()
        chartFrame.empty()
        tableFrame=st.container()
        tableFrame.empty()
        st.session_state.saveDayta=True
        if btnGo:
            updateResultPair(); tableRequested()
            #save this result to database?
        if st.session_state.saveDayta:  # st.session_state['t_a_Pack']:
            userinputFrame=st.container()
            userQuestFrame=st.empty()
            userQuestCols=userQuestFrame.columns([8.5,2])
            tempDisp=userQuestCols[0].empty()
            dataSaved=userQuestCols[1].form_submit_button("Save Data")
            if dataSaved:  #st.session_state['t_a_Pack']   st.session_state.saveDayta
                #updateResultPair(); tableRequested()
                #with st.form("frmUnikResult"):
                if st.session_state.theFormattedTytl != "": 
                    st.session_state.confirmSave+=1
                    userinputFrame.write("---")
                    formattedTytl = '<p style="font-family:Arial; text-align: left; color:brown; font-weight: bold; font-style: italic; font-size: 25px;">'+"Save Data 💾"+'</p>'
                    userinputFrame.markdown(formattedTytl, unsafe_allow_html=True)
                    resultFrame=userinputFrame.columns([1,0.5,1])
                    projName=resultFrame[0].text_input('Project Name*', placeholder="Project Name", key="projName")
                    projVersion=resultFrame[1].text_input('Revision No.*', placeholder="Revision No.", key="projVersion")
                    projClient=resultFrame[2].text_input('Client*', placeholder="Project Client", key="projClient")
                    projComment=userinputFrame.text_area('Comment:', placeholder="Enter a comment here...", key="projComment")
                    saveThisSession(projName, projVersion, projClient, projComment)
                else:
                    tempDisp.info("No data available.", icon="ℹ️")
                    sleep(2); tempDisp.empty()
                
            
if st.session_state.selected=="Review":
    # --- DATABASE INTERFACE ---
    def get_all_sessions():
        items = db.fetch_all_sessions()
        sessionDatas = [item["key"] for item in items]
        return sessionDatas

    subTytl, OFx_img, blNk=st.columns([10,1,2])
    theFormattedTytl = '<p style="font-family:Arial; text-align: left; color:brown; font-weight: bold; font-style: italic; font-size: 25px;">'+"Review Data 🗺️"+'</p>'
    subTytl.markdown(theFormattedTytl, unsafe_allow_html=True); savedData_DF=None; columnsOfExstingData=[[] for i in range(6)]
    colHdr=["Project Name", "Revision", "Client", "Date", "Time", "Comment"]
    dbKeys=["projName", "projVersion", "projClient", "date_saved", "time_saved", "projComment"]
    with st.form("saved_sessions"):
        getAllSessions=get_all_sessions()
        for k in getAllSessions:
            for i, j in enumerate(dbKeys):
                columnsOfExstingData[i].append(dict(list(db.get_session(k).items()))[j])

        savedData_DF=get_df2(colHdr, columnsOfExstingData)
        gd = GridOptionsBuilder.from_dataframe(savedData_DF)
        gd.configure_pagination(enabled=True)
        gd.enableRangeSelection=True
        gd.configure_selection(selection_mode='single', use_checkbox=True)

        gridoptions=gd.build()
        grid_table = AgGrid(savedData_DF,
                            gridOptions=gridoptions,
                            update_mode= GridUpdateMode.MODEL_CHANGED,
                            fit_columns_on_grid_load=True,
                            height = 200,
                            allow_unsafe_jscode=True,
                            enable_enterprise_modules = True,
                            theme = 'alpine')  # 'streamlit')
        sel_ro = grid_table["selected_rows"]
        userRequestFrame=st.empty()
        userRequestCols=userRequestFrame.columns([8.5,2])
        submitted=userRequestCols[1].form_submit_button("Load Data")
        tempDisp=st.empty()
        if submitted:
            tempDisp=st.empty()
            try:
                if not(sel_ro):1/0  # check if dataset has been selected
                dataDescription=""
                for hdr in colHdr[:5]:
                    dataDescription+=sel_ro[0][hdr]
                    if hdr!=colHdr[:5][-1]:dataDescription+=" - "
            except:
               tempDisp.empty();tempDisp.info("You must select a dataset to continue.", icon="ℹ️");sleep(2); tempDisp.empty()
            # try to get data from database
            try:
                session_data = db.get_session(dataDescription)
                st.session_state['t_a_Pack_noDF'] = session_data.get("t_a_Pack")
                st.session_state['t_a_Pack'] = {list(st.session_state['t_a_Pack_noDF'].keys())[k]:pd.DataFrame(list(st.session_state['t_a_Pack_noDF'].values())[k]) for k in range(len(st.session_state['t_a_Pack_noDF']))}
                st.session_state['theLines']=[x for x in st.session_state['t_a_Pack'].keys()]
                st.session_state.theFormattedTytl = '<p style="font-family:Arial; text-align: left; color:cyan; font-weight: bold; font-style: italic; font-size: 25px;">'+"Review Saved Data 📖"+'</p>'
                tempDisp.empty(); tempDisp.success("Data loaded successfully", icon="✅"); sleep(2); tempDisp.empty()
            except:
                tempDisp.empty(); st.warning("You must select a dataset to continue.", icon="ℹ️"); sleep(2); tempDisp.empty()
