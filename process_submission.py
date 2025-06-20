import cv2
import numpy as np
from typing import Dict, Tuple, List
import base64
import requests
import xml.etree.ElementTree as ET
import json
from openai import OpenAI
import sqlite3
import time
import pyodbc
import os
from io import BytesIO
from PIL import Image
from azure.storage.blob import BlobServiceClient
from cv2 import aruco
from datetime import datetime
import pandas as pd
import re
from pathlib import Path


os.system('cls')

# OpenAI API Key
sharath_api_key = "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"
server = "jskdsdj458.database.windows.net"
database = "zxncbzxcb"
username = "sharvas45"
password = "Demo@123"
turn_token = 'eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJUdXJuIiwiZXhwIjoxNzYzNjQ0NzQxLCJpYXQiOjE3MzI3MTQ4NDMsImlzcyI6IlR1cm4iLCJqdGkiOiI5NzQzMDAyOS03YjkyLTQ2ZGItODEyYS0zMjc2NGYwNGNmYTgiLCJuYmYiOjE3MzI3MTQ4NDIsInN1YiI6Im51bWJlcjo0NzE5IiwidHlwIjoiYWNjZXNzIn0.1kSZPQCgDL5xq-yTiTZjuR836vsGCDwILwV3kDKltoB2VeVO4V9AmbqFNetouZgT8H4C7oPysmuOw9j1ftUVJw'
blob_connection_string = "DefaultEndpointsProtocol=https;AccountName=uploadedpics;AccountKey=hgtQ5B5oN+UTMiigp0otdYbTBm2aPDx2ABF1a8Q4VgIzySeXlE4HoYc2KRqwEHyaCRym2CAW98Ol+AStjwgNfA==;EndpointSuffix=core.windows.net"
blob_container_name = "charts"
marker_size=80
aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
MAX_BATCH_SIZE=1000

connection_string = (
                f'DRIVER={{ODBC Driver 18 for SQL Server}};'
                f'SERVER={server};'
                f'DATABASE={database};'
                f'UID={username};'
                f'PWD={password};'
                'Encrypt=yes;'
                'TrustServerCertificate=no;'
            )
s_conn = pyodbc.connect(connection_string)
s_cursor = s_conn.cursor()


def get_metadata(testid):
    query=f"""
                SELECT  [question_no]
                    ,[x]
                    ,[y]
                    ,[w]
                    ,[h]
                    ,[ques_type]
                    ,[expected_answers],
                    [ai_prompt]
                FROM [ai_cms]
                where test_id='{testid}'
                and question_no is not null
                order by question_no asc
    """
    try:
        s_cursor.execute(query)
        rows = s_cursor.fetchall()
        # Convert to dictionary format
        metadata = {}
        for row in rows:
            metadata[row.question_no] = {
                'x': row.x,
                'y': row.y,
                'w': row.w,
                'h': row.h,
                'type': row.ques_type,
                'expected_answer': row.expected_answers,
                'ai_prompt':row.ai_prompt
            }
        return metadata
 
    except pyodbc.Error as e:
        print(f"Error in get_metadata: {str(e)}")
        raise



#get all pending assessments that have been submitted on Whatsapp
def get_pending_assessments(school,cycle,program): 
        query = f"""
                                        
                    WITH RankedSubmissions AS (
                        SELECT 
                            formid, 
                            completed_time, 
                            submission_link, 
                            assessment_cycle, 
                            assessment_program, 
                            student_name, 
                            student_school, 
                            student_class, 
                            student_section, 
                            student_id, 
                            source,
                            ROW_NUMBER() OVER (
                                PARTITION BY student_id 
                                ORDER BY completed_time DESC
                            ) AS rn
                        FROM ai_submissions
                        WHERE 
                            submission_link IS NOT NULL     
                            AND LEN(submission_link) > 4
                            AND student_school = '{school}'
                            AND assessment_cycle = '{cycle}'
                            AND assessment_program = '{program}'
                            AND processed = 0
    
                    )
                    SELECT 
                        formid, 
                        completed_time, 
                        submission_link, 
                        assessment_cycle, 
                        assessment_program, 
                        student_name, 
                        student_school, 
                        student_class, 
                        student_section, 
                        student_id, 
                        source
                    FROM RankedSubmissions
                    WHERE rn = 1
                    ORDER BY completed_time desc;
        """
        try:
            s_cursor.execute(query)
            rows = s_cursor.fetchall()
            print(f"Found {len(rows)} assessments pending processing")
            return rows
        except pyodbc.Error as e:
            print(f"Error in get_pending_assessments: {str(e)}")
            raise

#once a assessment submitted is processed, it is marked as processed in the db
def update_processed(df,batch_job_id,status,program,cycle,school):
    query1 = """
        UPDATE ai_submissions
        SET processed = ?
        WHERE formid = ?
    """

    query2 = """
        INSERT INTO ai_batch_queries 
        (batch_name, time_create, processed,program,cycle,school)
        VALUES (?, ?, 0,?,?,?)
    """

    query3="""delete from ai_student_levels
              where student_id=?
              and program=?
              and cycle=?
              and school=?
    """

    query4="""insert into ai_student_levels
                (student_id,program,cycle,school,s_class,section,image_url)
                values(?,?,?,?,?,?,?)
    """


    try:
        for _, row in df.iterrows():
            formid = row['formid'] 
            student_id = row['student_id'] 
            student_class = row['student_class']
            student_section = row['student_section']
            url = row['url']
            print(f"""Now updating {student_id}\n""")
            s_cursor.execute(query1,(status,formid))
            s_cursor.execute(query3,(student_id,program,cycle,school))
            s_cursor.execute(query4,(student_id,program,cycle,school,student_class,student_section,url))
        s_cursor.execute(query2, (batch_job_id,int(time.time()),program,cycle,school))
        s_cursor.commit()
    except pyodbc.Error as e:
        print(f"Error in update_processed: {str(e)}: {query2}")
        raise        

#preprocessing, which extracts all content inside the big black rectangular box, rotates the image if requires and resizes
#the image to make it standard
#preprocessing, which extracts all content inside the big black rectangular box, rotates the image if requires and resizes
#the image to make it standard
def crop_and_align_document(image_path, min_area=100, aspect_ratio_range=(0.5, 2.0)):
    image = cv2.imread(image_path)
    if image is None:
        return None

    # Convert to grayscale for marker detection
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Detect ArUco markers
    corners, ids, _ = aruco.detectMarkers(gray, aruco_dict)

    # This should not happen as I have already detected the Aruco markers at image capture time.
    if ids is None or len(ids) < 4:
        raise ValueError("Could not detect all four markers")

    # Sort corners by marker IDs (assuming IDs 0,1,2,3 for TL, TR, BL, BR)
    sorted_markers = sorted(zip(ids.flatten(), corners), key=lambda x: x[0])
    src_points = np.float32([marker[1][0][0] for marker in sorted_markers])  # Extract first corner of each marker

    # Estimate the original document size (including markers)
    doc_width = 500 + 2 * marker_size  # Adjust width based on original document
    doc_height = 700 + 2 * marker_size  # Adjust height based on original document

    dst_points = np.float32([
        [0, 0],  # Top-left
        [doc_width, 0],  # Top-right
        [0, doc_height],  # Bottom-left
        [doc_width, doc_height]  # Bottom-right
    ])

    # Compute perspective transform matrix
    matrix = cv2.getPerspectiveTransform(src_points, dst_points)

    # Apply perspective transform
    aligned = cv2.warpPerspective(image, matrix, (doc_width, doc_height))

    output_size = (1240, 1754)
    target_height = 1754
    target_width = 1240

    # Use Lanczos interpolation which often gives better results for text
    resized_img = cv2.resize(aligned, (target_width, target_height), 
                            interpolation=cv2.INTER_LANCZOS4)
                            

    return resized_img

#get the submitted image from turn api
def fetch_submission(submission_link,student_id,school,cycle,program):
    try:
        url = f'https://whatsapp.turn.io/v1/media/{submission_link}'
        headers = {'Authorization': f'Bearer {turn_token}'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        image_data = BytesIO(response.content) 
        image = Image.open(image_data)
        image.verify()
        image_name = f"{student_id}.jpg"
        image_path = Path(f"C:/Users/Admin/Downloads/ai_assess/{program}/{cycle}/{school}/full_images/{image_name}")
        
        image_path.parent.mkdir(parents=True, exist_ok=True)

        with open(image_path, 'wb') as file:
            file.write(response.content)
        return image_path    
    except Exception as e:
         print("error in fetch_submission")
         return None    

def update_student_response(df):
    try:
        unique_rows = df[['student_id', 'program', 'cycle']].drop_duplicates()

        #first delete
        for _, row in unique_rows.iterrows():
            student_id = row['student_id']
            print(f"""Now updating responses for {student_id}""")
            program = row['program']
            cycle = row['cycle']
            query = """
                DELETE FROM dbo.ai_student_responses 
                WHERE upper(student_id) = ? AND upper(program) = ? AND upper(cycle) = ?
            """
            s_cursor.execute(query, (student_id.upper(), program.upper(), cycle.upper()))

        s_cursor.commit()
        
        #then insert
        query = """INSERT INTO dbo.ai_student_responses 
                    (question_no, given_answer, ai_correct, is_correct, formid, student_id, program, cycle, ai_analysis, requires_human)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
        rows = df.values.tolist()
        s_cursor.executemany(query, rows)
        s_cursor.commit()
    except pyodbc.Error as e:
        print(f"Error in update_student_response: {str(e)}")
        raise
    except Exception as e:
        print("Error in update_student_response function")
        raise    


def get_pending_batches(school,cycle,program):
    query = f"""
        SELECT  batch_name,
        program,
        cycle
       FROM ai_batch_queries 
       where processed = 0 and
       school='{school}'
       and cycle='{cycle}'
       and program='{program}'
        """
    try:
        s_cursor.execute(query)
        rows = s_cursor.fetchall()
        print(f"Found {len(rows)} batches pending processing")
        return rows
    except pyodbc.Error as e:
        print(f"Error in get_pending_batches: {str(e)}")
        raise

def upadate_batch_completeion(batchid):
    query = f"""
        update  ai_batch_queries
        set processed= 1
        where batch_name='{batchid}'
        """
    try:
        s_cursor.execute(query)
        s_cursor.commit()
    except pyodbc.Error as e:
        print(f"Error in upadate_batch_completeion: {str(e)}")
        raise
        


def retrieve_pending_level_updates(school,cycle,program):
    query1= f"""select student_id from ai_student_levels where upper(school) = upper('{school}') and level is NULL
                and upper(program)=upper('{program}') and upper(cycle) = upper('{cycle}')"""

    query2 = f"""select question_no, is_correct from
                 ai_student_responses 
                 where upper(program)= ?
                 and upper(cycle) = ?
                 and student_id=? order by question_no asc"""
                      
    try:
        s_cursor.execute(query1)
        rows = s_cursor.fetchall()
        print(f"Found {len(rows)} Level pending processing")
        for row in rows:
            student_id = row[0]
            stu_df = pd.read_sql_query(query2,s_conn,params=[program,cycle,student_id])
            stu_level=determine_level(stu_df,program)
            update_level(student_id, stu_level, school,cycle,program)
    except pyodbc.Error as e:         
        print(f"Error in get_pending_level_updates: {str(e)}")

#Determine the student level based on the accuracy of each answer
def determine_level(df,program):
    if (program.upper()=="FM"):
        
        level1_ques=["a","b","c","d"]
        level1_data = df[df['question_no'].isin(level1_ques)]
        total_correct = level1_data['is_correct'].sum()
        if(total_correct<=2): return "Level 1"

        level2_ques=["e","f","g","h"]
        level2_data = df[df['question_no'].isin(level2_ques)]
        total_correct = level2_data['is_correct'].sum()
        if(total_correct<=2): return "Level 2"

        level3_ques=["i","j","k","l"]
        level3_data = df[df['question_no'].isin(level3_ques)]
        total_correct = level3_data['is_correct'].sum()
        if(total_correct<=2): return "Level 3"

        level4_ques=["m","n","o","p"]
        level4_data = df[df['question_no'].isin(level4_ques)]
        total_correct = level4_data['is_correct'].sum()
        if(total_correct<=2): return "Level 4"

        return "Level 5"

    if (program=="FR"):
        letter_questions = ['q1.1', 'q1.2', 'q1.3']
        letter_level_data = df[df['question_no'].isin(letter_questions)]
        total_correct = letter_level_data['is_correct'].sum()
        if(total_correct<=1): return "Letter Level"

        cvc_questions = ['q2.1','q2.2','q2.3','q3.1','q3.2','q3.3']
        cvc_level_data = df[df['question_no'].isin(cvc_questions)]
        total_correct = cvc_level_data['is_correct'].sum()
        if(total_correct<=3): return "CVC Level"

        word_questions = ['q4.1','q4.2','q4.3','q5','q6.1','q6.2','q6.3','q6.4','q6.5']
        word_level_data = df[df['question_no'].isin(word_questions)]
        total_correct = word_level_data['is_correct'].sum()
        
        if(total_correct<=5):
            return "Word Level" 
        else: 
            return "Sentence Level"

#update the levels in the db
def update_level(student_id, stu_level, school,cycle,program):
    #The level_dict is just to make sure the levels are retrieved in the right order at the time of retrieving.
    #e.g. Letter comes first, then CVC etc.
    level_dict = {
                "Letter Level": {"age": 1},
                "CVC Level": {"age": 2},
                "Word Level":{"age":3},
                "Sentence Level":{"age":4},
                "Level 1":{"age":1},
                "Level 2":{"age":2},
                "Level 3":{"age":3},
                "Level 4":{"age":4},
                "Level 5":{"age":5},
                }
    try:
        print(f"""Working on {student_id} """)
        query=f"""update ai_student_levels 
        set level='{stu_level}',
        level_order='{level_dict[stu_level]["age"]}'
        where student_id='{student_id}'
        and program='{program}'
        and cycle='{cycle}'
        and school='{school}'"""
        #print(query)
        s_cursor.execute(query)
        s_cursor.commit()
    except pyodbc.Error as e:
        print(f"Pyodbc Error in update_level: {str(e)}")
        raise
    except Exception as e:
        print(f"Error in update_level: {str(e)}")   




 
def retrieve_batches(client,metadata,school,cycle,program):
    pending_batches = get_pending_batches(school,cycle,program)
    for batch in pending_batches:
        batchid = batch[0]
        program = batch[1]
        cycle = batch[2]

        data_list=[]

        # Keep retrying until the batch is completed
        while True:
            batch_job = client.batches.retrieve(batchid)
            if batch_job.status == "completed":
                break
            else:
                print(f"Batch {batchid} is still processing. Retry later...")
                break
                #time.sleep(100)

        if (batch_job.status=="completed"):
            print(f"""Currently processing {batchid}""")
            result_file_id = batch_job.output_file_id
            result = client.files.content(result_file_id).content
            result_file_name = f"C:/Users/Admin/Downloads/ai_assess/json/{batchid}.jsonl"
                        
            #write the batch result to a JSON
            with open(result_file_name, 'wb') as file:
                file.write(result)

            with open(result_file_name, 'r') as file:
                for line in file:
                    try:
                        data = json.loads(line)
                        custom_id = data['custom_id']
                        custom_id = custom_id.strip()
                        parts = custom_id.split(":::")
                        formid = parts[0]
                        student_id = parts[1]
                        ques_index = parts[2]
                        expected_answer = metadata[ques_index]['expected_answer'].strip().lower()
                        choices = data['response']['body']['choices']
                                
                        for choice in choices:
                            content_str = choice['message']['content']
                            clean_content = re.sub(r'```json\n|\n```', '', content_str)
                            content_json = json.loads(clean_content)
                            result = content_json.get('Result', '')
                            analysis = content_json.get('Analysis', '')
                            result = re.sub(r"[\s-]+", "", result) 

                            if result.strip().lower() == expected_answer:
                                ai_correct =1
                            else:
                                ai_correct=0  

                            is_correct = ai_correct       

                            #need to update this logic
                            if ai_correct ==0:
                                requires_human =1
                            else:
                                requires_human = 0


                            data_list.append({
                                    'question_no': ques_index.strip().lower(),
                                    'given_answer': result.strip().lower(),
                                    'ai_correct':ai_correct,
                                    'is_correct': is_correct,
                                    'formid':formid,
                                    'student_id':student_id,
                                    'program':program,
                                    'cycle':cycle,
                                    'ai_analysis':analysis,
                                    'requires_human':requires_human
                                    })                                      

                    except json.JSONDecodeError:
                        data_list.append({
                                    'question_no': ques_index.strip().lower(),
                                    'given_answer': "no answer",
                                    'ai_correct':0,
                                    'is_correct': 0,
                                    'formid':formid,
                                    'student_id':student_id,
                                    'program':program,
                                    'cycle':cycle,
                                    'ai_analysis':"no analysis",
                                    'requires_human':1
                                    })
                        print(f"""{student_id} - {ques_index} - no answer found""") 
                        
            df = pd.DataFrame(data_list)                       
            update_student_response(df)
            upadate_batch_completeion(batchid)
            s_cursor.commit()
        else:
            print("Some batches are still processing. Please try after some time!")

def process_submissions(client,metadata,school,cycle,program):

    pending_assessments  = get_pending_assessments(school,cycle,program)
    
    current_batch_size = 0
    total_ass_processed = 0
    rows = [] 
    total_ass_pending = len(pending_assessments)

    tasks = []

    for assessment in pending_assessments:
        total_ass_processed = total_ass_processed +1
        # Load image and pre-process it
        print(f"""Processing {total_ass_processed}:{assessment.student_id}""")
        image_path = fetch_submission(assessment.submission_link, assessment.student_id, school,cycle,program)
        if image_path is None:
            print("Unble to fetch image from WhatsApp")
            continue
        processed_image = crop_and_align_document(image_path)
        filename, file_extension = os.path.splitext(image_path)
        output_path = f"{filename}-preprocessed{file_extension}"

        if processed_image is None:
             print(f"""Unable to process the image for submission with formID: {assessment.formid}""")
             continue

        cv2.imwrite(output_path, processed_image)
        

        #upload to azure. 
        blob_name= assessment.formid
        blob_service_client = BlobServiceClient.from_connection_string(blob_connection_string)
        container_client = blob_service_client.get_container_client(blob_container_name)

        with open(output_path, "rb") as data:
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(data, content_type="image/jpeg", overwrite=True)
        uploaded_url = blob_client.url

        row = {
                'formid': assessment.formid,
                'student_id': assessment.student_id,
                'url':uploaded_url,
                'student_school':assessment.student_school,
                'student_class': assessment.student_class,
                'student_section':assessment.student_section

            }
        rows.append(row)

        #xtract each field
        for field_name, field_properties in metadata.items():
            ques_index = field_name
            ques_x= field_properties['x']
            ques_y = field_properties['y']
            ques_w = field_properties['w']
            ques_h= field_properties['h']
            ques_type= field_properties['type']
            expected_answer= field_properties['expected_answer']
            current_batch_size = current_batch_size+1

            cropped = processed_image[ques_y:ques_y+ques_h, ques_x:ques_x+ques_w]

            save_path = f"""C:/Users/Admin/Downloads/ai_assess/{program}/{cycle}/{school}/{ques_index}"""
            filename = f"{assessment.student_id}.jpg"
        
            # Ensure the directory exists
            os.makedirs(save_path, exist_ok=True)

            # Save the cropped image
            file_path = os.path.join(save_path, filename)
            cv2.imwrite(file_path, cropped)
            _, img_bytes = cv2.imencode('.jpg', cropped)
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')

            #for each question type link the coresponding prompt type
            math_prompt= """
                You are a handwriting analysis expert. Look at the writing *inside* the box.
                
                Expected answer is 
                <expected_answer>
                    {{expected_answer}}
                </expected_answer>

                Respond in the following JSON format:

                    {
                    "Result": "What is written inside the box?"
                    "Analysis":"How many digits are there? How are the number written? Mention the shape of strokes, loops, slants, spacing, alignment, size, and anything else that describes the way it visually appears.
                    Has the student scratched, overwritten the answer? Be as specific and visual as possible, as if explaining to someone who cannot see the image."
                    }
            """

            mcq_prompt= """Examine the provided MCQ answer image as a handwriting analysis expert.
                Tasks:
                Numbering: Assign sequential IDs (from 1) to all checkboxes in a strict top-left, then left-to-right, then top-to-bottom reading order.
                Identify Checked: A box is checked ONLY if it contains a clear ✓ or a deliberate filled mark within or overlapping its boundary. Ignore small dots, printing artifacts, shadows, or discoloration.
                Exclude: Ignore checkboxes that are: empty; have only scribbles, 'X', or circles; have overwritten/crossed-out checks; or show smudges/faint/partial marks.
                Output JSON:
                JSON

                {
                "Result": "Which option numbers are selected (e.g., '2' or '2,3')",
                "Analysis": "What other handwritten marks do you see?"
                }

            """

            sa_prompt="""
                         You are a handwriting analysis expert. Look at the writing *inside* the box.
                
                Expected answer is 
                <expected_answer>
                    {{expected_answer}}
                </expected_answer>
                The expected answer can only contain alphabets.
                Remove ALL spaces, hyphens, and punctuation.


                Respond in the following JSON format:

                    {
                    "Result": "What is written inside the box?"
                    "Analysis":"How many alphabets are there? How are the alphabets written? Mention the shape of strokes, loops, slants, spacing, alignment, size, and anything else that describes the way it visually appears.
                    Has the student scratched, overwritten the answer? Be as specific and visual as possible, as if explaining to someone who cannot see the image."
                    }
            """   
        

            match ques_type.upper():
                case "MCQ": prompt = mcq_prompt
                case "SA": prompt= sa_prompt.replace("{expected_answer}",expected_answer)                
                case "NAME": prompt =prompt
                case "MATH": prompt = math_prompt.replace("{expected_answer}",expected_answer)

            task = {
            "custom_id": f"{assessment.formid}:::{assessment.student_id}:::{ques_index}", 
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                # This is what you would have in your Chat Completions API call
                "model": "gpt-4o-mini",
                "temperature": 0,
                "max_tokens": 1000,
                "messages": [
                    {
                        "role": "system",
                        "content": prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": ques_index
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_base64}"
                                }
                            },
                        ],
                    }
                ]            
            }
        }
            tasks.append(task) 
        
        if (current_batch_size>MAX_BATCH_SIZE and field_name.upper() in ('P','Q6.5')) or (total_ass_processed == total_ass_pending and field_name.upper() in ('P','Q6.5')):
            
                #Wait till chatgpt is available
            while True:
                batches = client.batches.list()
                # Count the total number of batches with specific statuses
                total_batches = sum(1 for batch in batches.data if batch.status in ['validating', 'in_progress'])   
                print("Currently total batches running: "+ str(total_batches))      
            
                if total_batches < 5:  # Proceed only if total_batches is less than 10
                    break
                
                print(f"Batch limit exceeded ({total_batches} batches). Sleeping for a while...")
                time.sleep(60)  # Sleep for 60 seconds before checking again
       
            
            file_name = "batch.jsonl"
            with open(file_name, 'w') as file:
                for obj in tasks:
                    file.write(json.dumps(obj) + '\n') 

            batch_file = client.files.create(
                file=open(file_name, "rb"),
                purpose="batch"
            )    

            batch_job = client.batches.create(
                input_file_id=batch_file.id,
                endpoint="/v1/chat/completions",
                completion_window="24h"
            )  

            batch_job = client.batches.retrieve(batch_job.id)  

            print (f"""{datetime.now()} - Created {batch_job.id}\n""")
    
            update_df = pd.DataFrame(rows)
            update_processed(update_df,batch_job.id,1,program,cycle,school)
            s_conn.commit()
            current_batch_size=0
            rows=[]
            tasks = []
        
def main():
    print("****Welcome to LearnLens Processing***\n")
    client = OpenAI(api_key = sharath_api_key)
    testid=input("Enter Testid")
    metadata = get_metadata(testid)
    school= input("Enter School: ")
    cycle= input("Cycle: ")
    program=input("Program: ")
 

    inp= input("""Press 1 to process student submissions
               Press 2 to retrieve batches from OpenAI
               Press 3 to update levels\n""")
    
    if inp == '1':process_submissions(client,metadata,school.upper(), cycle.upper(),program.upper())   
    elif inp=='2':retrieve_batches(client,metadata,school,cycle,program)
    elif inp=='3':retrieve_pending_level_updates(school,cycle,program)
    else:    
        print("Incorrect option chosen")    
    s_conn.commit()
    s_conn.close()

if __name__ == "__main__":
    main()