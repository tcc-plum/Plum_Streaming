import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from emotion import face_emotion
import uuid
import base64
import cv2
import os
import random
from persistence import MySQL
import threading

class Watcher:
    
    DIRECTORY_TO_WATCH = '../Plum_Research/frames'

    def __init__(self):
        self.observer = Observer()

    def run(self):
        event_handler = Handler()
        self.observer.schedule(event_handler, self.DIRECTORY_TO_WATCH, recursive=True)
        self.observer.start()
        try:
            while True:
                # time.sleep(5)
                time.sleep(1)
        except:
            self.observer.stop()
            print("Error")

        self.observer.join()


class Handler(FileSystemEventHandler):

    @staticmethod
    def on_any_event(event):
        if event.is_directory:
            return None

        elif event.event_type == 'created':
            
            face = DetectFaces()
            
            try:
                if(face.detect(event.src_path)):
                    print('Rosto detectado no arquivo - {}'.format(event.src_path))
                    resultado = face_emotion(event.src_path)
                    
                    # id_documento = face.biometria(resultado, event.src_path)
                    # print('Documento {} inserido com sucesso!'.format(id_documento))
                    th = threading.Thread(target=face.biometria, args=(resultado, event.src_path))
                    th.start()
                    
                    # os.remove(event.src_path)
                else:
                    print('Nenhum rosto detectado no arquivo - {}'.format(event.src_path))
                    if os.path.isfile(event.src_path):
                        os.remove(event.src_path)
            except:
                print('[ERRO] Falha ao detectar rosto ou armazenar as informações')
                if os.path.isfile(event.src_path):
                    os.remove(event.src_path)

class DetectFaces:
    
    def detect(self, image):
        classificador_facial = cv2.CascadeClassifier('modelo/frontal/haarcascade_frontalface_default.xml')
        image_to_classify = cv2.imread(image)
        min_size = (image_to_classify.shape[1], image_to_classify.shape[0])
        min_frame = cv2.resize(image_to_classify, min_size)
        detected_faces = classificador_facial.detectMultiScale(min_frame)
        for face in detected_faces:
            x_axis, y_axis, width, height = [vertice for vertice in face]
            sub_face = image_to_classify[y_axis:y_axis+height, x_axis:x_axis+width]
            return True
        return False
    
    def biometria(self, documento, diretorio_local):
        if documento['resposta']['status'] == 'sucesso':
            dispositivo = ['entrada','saida']
            indice = random.randint(0,1)
            documento['dispositivo'] = dispositivo[indice]
            dir_local = diretorio_local
            dir_local = str(dir_local).replace(os.sep, '/') 
            documento['local_dir'] = dir_local
            
            with open(dir_local, 'rb') as arquivo:
                imagem = arquivo.read()
            
            blob = base64.b64encode(imagem)
            documento['blob'] = blob.decode('utf-8')
            
            os.remove(dir_local)
            
            guid = self.salvarDB(documento)
            
            print('[INFO] Documento {} inserido na Thread'.format(guid))
            return guid
        else:
            print('[WARNING] A tag status não é sucesso')
            os.remove(diretorio_local)
            
    def salvarDB(self, documento):
        
        id = uuid.uuid4()
        id = str(id).replace('_', '')
        id = str(id).replace('-', '')
        id = str(id).replace('/', '')
        
        json_string = {id : documento}
        
        try:                      
            self.insereMySQL(id, json_string)
        except:
            print('[ERRO] Registros não inseridos no MySQL')
        
        return str(id)
    
    def insereMySQL(self, id, json_string):
        mysql = MySQL()
        sentimentos = ["irritação", "náusea", "medo", "felicidade", "tristeza", "surpresa", "neutralidade"]
        
        ## Documento
        HashID = id
        Data = json_string[HashID]['resposta']['data']
        
        fk = mysql.inserir_documento(HashID, Data)
        
        ## Foto
        Nome = json_string[HashID]['resposta']['foto']['nome']
        Largura = json_string[HashID]['resposta']['foto']['largura']
        Altura = json_string[HashID]['resposta']['foto']['altura']
        Local = json_string[HashID]['local_dir']
        Dispositivo = json_string[HashID]['dispositivo']
        Imagem = json_string[HashID]['blob']
        
        mysql.inserir_foto(Nome, Largura, Altura, Local, Dispositivo, Imagem, fk)
        
        ## Sentimento        
        for i in range(0, 7):
            Descricao = sentimentos[i]
            Valor = json_string[HashID]['resposta']['sentimentos'][Descricao]['valor']
            Confianca = json_string[HashID]['resposta']['sentimentos'][Descricao]['confiança']
            mysql.inserir_sentimento(Descricao, Valor, Confianca, fk)
                
        ## Pessoa
        Genero = json_string[HashID]['resposta']['gênero']['valor']
        Confianca_G = json_string[HashID]['resposta']['gênero']['confiança']
        Idade = json_string[HashID]['resposta']['idade']['valor']
        Confianca_I = json_string[HashID]['resposta']['idade']['confiança']
        
        mysql.inserir_pessoa(Genero, Confianca_G, Idade, Confianca_I, fk)
