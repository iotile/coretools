import tornado.web

class IndexHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def get(self):
        self.write("This is your response")
        self.finish()
