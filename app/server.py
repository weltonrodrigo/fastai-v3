from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
import uvicorn, aiohttp, asyncio
import os
import uuid
from io import BytesIO

from fastai import *
from fastai.vision import *

export_file_url = 'https://drive.google.com/uc?export=download&id=13Nxml5y0VVrn7J8GjTuxZDO1WwR2YslX'
export_file_name = 'export.pkl'

classes = ['macbook', 'notmacbook']
path = Path(__file__).parent

app = Starlette()
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_headers=['X-Requested-With', 'Content-Type'])
app.mount('/static', StaticFiles(directory='app/static'))

async def download_file(url, dest):
    if dest.exists(): return
    async with aiohttp.ClientSession() as session:
        print('Saving model...')
        async with session.get(url) as response:
            data = await response.read()
            with open(dest, 'wb') as f: f.write(data)
            print('Done')

async def setup_learner():
    await download_file(export_file_url, path/export_file_name)
    try:
        learn = load_learner(path, export_file_name)
        return learn
    except RuntimeError as e:
        if len(e.args) > 0 and 'CPU-only machine' in e.args[0]:
            print(e)
            message = "\n\nThis model was trained with an old version of fastai and will not work in a CPU environment.\n\nPlease update the fastai library in your training environment and export your model again.\n\nSee instructions for 'Returning to work' at https://course.fast.ai."
            raise RuntimeError(message)
        else:
            raise

loop = asyncio.get_event_loop()
tasks = [asyncio.ensure_future(setup_learner())]
learn = loop.run_until_complete(asyncio.gather(*tasks))[0]
loop.close()

@app.route('/')
def index(request):
    html = path/'view'/'index.html'
    return HTMLResponse(html.open().read())

@app.route('/analyze', methods=['POST'])
async def analyze(request):
    uuid_str = str(uuid.uuid4())
    data = await request.form()
    img_bytes = await (data['file'].read())
    img = open_image(BytesIO(img_bytes))
    prediction = learn.predict(img)[0]
    img.save(f'images/%s.png' % uuid_str)
    return JSONResponse({'result': str(prediction), 'classes': classes, 'img_id': uuid_str})

@app.route('/report', methods=['POST'])
async def report(request):
    report = await request.json()
    for clazz in classes:
        if not os.path.exists('images/%s' % clazz): os.makedirs('images/%s' % clazz)

    os.rename('images/%s.png' %  report['img_id'], 'images/%s/%s.png' % (report['class'], report['img_id']))
    return RedirectResponse(url='/')

if __name__ == '__main__':
    if 'serve' in sys.argv:
        port = int(os.getenv('PORT', 5042))
        uvicorn.run(app=app, host='0.0.0.0', port=port)
