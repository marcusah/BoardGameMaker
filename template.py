"Define the Template class and some template examples"
__author__ = 'MRS.OPOYEN'


from fields import Field
from kivy.properties import NumericProperty, OptionProperty, ObjectProperty, DictProperty, StringProperty, ObservableList, ListProperty, BooleanProperty
from fields import ImageField
from kivy.factory import Factory
from collections import OrderedDict
from editors import editors_map, FileEditor, TemplateFileEditor
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.carousel import Carousel
from conf import path_reader

class BGTemplate(Field, RelativeLayout):
    """Template class. Made of fields able to render an image"""
    Type = "TemplateField"
    template_name = StringProperty('TMPL')
    source = OptionProperty('text', options=['file', 'text'])
    not_exported = ['ids', 'print_index','template_name', 'src']
    src = StringProperty()

    #Now for the special attributes only used when printing the objects
    print_index = DictProperty()

    def __repr__(self):
        return '<Template #%s>'%self.template_name

    def add_widget(self, widget, index=0):
        #replacing index by z-index
        a = RelativeLayout.add_widget(self, widget, getattr(widget,'z',0))
        #Duplicate pointer to template
        widget.template = self
        #Re order them according to z elt:
        cs = self.children[:]
        cs.sort(key= lambda x: getattr(x,'z',0), reverse=True)
        self.children = cs
#        #Also reorder canvas
#        for cindex, c in enumerate(self.children):
#            if not self.canvas.indexof(c.canvas) == -1:
#                self.canvas.remove(c.canvas)
#            self.canvas.insert(0,c.canvas)

    @classmethod
    def FromFile(cls, filename):
        print 'From File with', filename
        name, filename = find_template_path(filename)
        #Load  & return all templates from a file as a list. Take an optionnal filter
        from kivy.lang import Builder
        # Remove any former trace of the file
        Builder.unload_file(filename)
        # Now create a widget
        try:
            Builder.load_file(filename)
            res = cls._process_file_build(filename)
        except Exception, E:
            from conf import log, alert
            import traceback
            alert(str(E))
            print '[Error] While trying to import Template ',filename
            log(E, traceback.print_exc())
            res = list()
        if name:
            return [r for r in res if r.template_name == name ]
        return res

    @classmethod
    def _process_last_build(cls):
        from kivy.lang import Builder
        #Get last rules imported for template creation
        k,r = Builder.rules[-1]
        p = r.ctx
        if not p.dynamic_classes:
            #Old school technique: get last rules
            from kivy.logger import Logger
            Logger.warn('Registering through old technique with .Klass:', k.key)
            t = BGTemplate()
            t.cls = (k.key,)
            Builder.apply(t)
            t.template_name = k.key
        else:
            kkey = p.dynamic_classes.keys()[0]
            t = Factory.get(kkey)()
            t.template_name = kkey
            #Now forcing id values to name
            for ID in t.ids:
                t.ids[ID].name = ID
        return t

    @classmethod
    def _process_file_build(cls,filename):
        from kivy.lang import Builder
        res = list()
        #factory unload
        # Get all rules from files
        rules = [x for x in Builder.rules if x[1].ctx.filename == filename]
        attrs= dict()
        ctxs = set()
        for k,r in rules:
            ctxs.add(r.ctx)
            attrs[k] = (k.match, r.properties.keys())
        for ctx in ctxs:
            #print ctx.dynamic_classes, ctx.rules
            #print ctx, ctx.directives
            for dclass in ctx.dynamic_classes:
                rule = list(r for s,r in ctx.rules if s.key == dclass.lower()).pop()
                #print dclass, rule
                t = Factory.get(dclass)()
                t.directives = [x[1] for x in ctx.directives]
                eval_context = dict()
                eval_context.update(t.ids)
                for _d in t.directives:
                    if _d.startswith('include'): continue#only doind import at this stage
                    if _d.startswith('set'):
                        n,v = _d[4:].split(" ",1)
                    elif _d.startswith('import'):
                        n,v = _d[7:].split(" ",1)
                    else:
                        print 'Unkown KV directives skipped',_d
                    eval_context[n] = v
                class prox:
                        value= 0
                _prox= prox()
                #print [(r.name, r.properties.get('z',_prox).value) for r in rule.children]
                rcs = []
                for r in rule.children:
                    rcs.append(r)
                    rcs.sort(key=lambda x: x.properties.get("z",_prox).value)
                rcs.reverse()
                    #simulate what has been done for template
                #print [(r.name, r.properties.get('z',_prox).value) for r in rcs]
                for tc,rc in zip(t.children, rcs):
                    #print tc, rc
                    for p,v in rc.properties.items():
                        if hasattr(tc,p) and getattr(tc,p) !=  v.co_value:
                            #Get code, it may be interessting
                            #but first, test if it is not simply a tuple or boolean:
                            if str(getattr(tc,p)) == str(v.value): continue
                            #print "Co Value test", tc, p, "'%s'"%getattr(tc,p), "'%s'"%v.value, str(getattr(tc,p)) == str(v.value)
                            if type(getattr(tc,p)) in (type(()), type(list()), ObservableList):
                                #try if we are not comparing simply stuff
                                try:
                                    _res = 0
                                    theval = eval(v.value, eval_context)
                                    if len(getattr(tc,p)) != len(theval):
                                        raise ValueError('Compared iterables do not have the same list size')
                                    for _v,_cv in zip(getattr(tc,p), theval):
                                        if _v!=_cv:
                                            _res+=1
                                    if not _res:
                                        #The list or tuple are the same => should not be considered as code.
                                        continue
                                except Exception, e:
                                    print 'Trying to guess code behing %s did not work'%p, e

                            tc.code_behind[p] = v.value
                if isinstance(t, BGTemplate):
                    t.template_name = dclass
                    for ID in t.ids:
                        #Force field name to ID
                        t.ids[ID].name = ID
                    #escape from recursion issue between on_src & from file
                    t.src = "@%s"%filename
                    if not t.attrs:
                        #force a reset of orederedict to avoid singleton effect
                        t.attrs = OrderedDict()
                        #fill attrs with default ones
                        for (m,ats) in attrs.values():
                            if m(t):
                                props = t.properties()
                                for pname in ats:
                                    pklass = props[pname]
                                    if pklass.__class__ == ObjectProperty:
                                        if getattr(t,pname).__class__ in editors_map:
                                            t.attrs[pname] = editors_map[getattr(t,pname).__class__]
                                    else:
                                        if pklass.__class__ in editors_map:
                                            t.attrs[pname] = editors_map[pklass.__class__]
                    res.append(t)
        return res

    @classmethod
    def FromText(cls, text):
        from kivy.lang import Builder
        #Now create a widget
        Builder.load_string(text)
        res = cls._process_last_build()
        return res

    @classmethod
    def FromField(cls, field):
        "Create a whole template base on a single field"
        class FromFieldTemplate(BGTemplate):
            def __init__(self, **kwargs):
                BGTemplate.__init__(self, **kwargs)
                self.template_name = "%s Wrapper"%field.Type
                self.add_widget(field.Copy())
                field.size = self.size
                self.attrs = field.attrs.copy()
        return FromFieldTemplate()

    def export_to_image(self, filename=None, bg_col = (1,1,1,0)):
        from kivy.graphics import Canvas, Translate, Fbo, ClearColor, ClearBuffers, Scale


        if filename is None:
            #resorting to default build on id
            filenmame = 'build/%s.png'%id(self)
        if self.parent is not None:
            canvas_parent_index = self.parent.canvas.indexof(self.canvas)
            self.parent.canvas.remove(self.canvas)

        fbo = Fbo(size=self.size, with_stencilbuffer=True)

        with fbo:
            ClearColor(*bg_col)
            ClearBuffers()
            Scale(1, -1, 1)
            Translate(-self.x, -self.y - self.height, 0)

        fbo.add(self.canvas)
        fbo.draw()
        fbo.texture.save(filename, flipped=False)
        fbo.remove(self.canvas)

        if self.parent is not None:
            self.parent.canvas.insert(canvas_parent_index, self.canvas)

        return True

    def toImage(self, bg_color=(1,1,1,0), for_print = False):
        #create image widget with texture == to a snapshot of me
        from kivy.graphics import Canvas, Translate, Fbo, ClearColor, ClearBuffers, Scale
        from kivy.core.image import Image as CoreImage

        if self.parent is not None:
            canvas_parent_index = self.parent.canvas.indexof(self.canvas)
            self.parent.canvas.remove(self.canvas)


        if for_print:# make all not printed element disappear
            disappear = set()
            from fields import BaseField
            for children in self.walk():
                if not isinstance(children, BaseField):
                    continue
                if children.printed:
                    continue
                disappear.add((children, children.opacity))
                children.opacity = 0

        fbo = Fbo(size=self.size, with_stencilbuffer=True)


        with fbo:
            ClearColor(*bg_color)
            ClearBuffers()
            Scale(1, -1, 1)
            Translate(-self.x, -self.y - self.height, 0)

        fbo.add(self.canvas)
        fbo.draw()

        cim = CoreImage(fbo.texture, filename='%s.png'%id(self))

        fbo.remove(self.canvas)

        if for_print:
            for (children, opacity) in disappear:
                children.opacity = opacity
        if self.parent is not None:
            self.parent.canvas.insert(canvas_parent_index, self.canvas)


        return cim

    def blank(self):
        t = self.__class__()
        t.cls = self.cls
        t.template_name = self.template_name
        t.Type = self.Type
        return t

    def apply_values(self, values):
        print 'appy_values', self, values
        childrens = self.ids.values()
        for k,v in values.items():
            if '.' not in k:
                for cname in self.ids.keys():
                    if cname == k and getattr(self.ids[cname],'default_attr'):
                        print 'resorting to default attr', self.ids[cname], k, getattr(self.ids[cname],'default_attr'), v
                        setattr(self.ids[cname], getattr(self.ids[cname],'default_attr'), v)
                        break
                else:
                    setattr(self,k,v)
            else:
                childName, attrName = k.split('.', 2)
                for cname in self.ids.keys():
                    if cname == childName:
                        if isinstance(self.ids[cname], ImageField):
                            self.ids[cname].source = v
                        setattr(self.ids[cname], attrName, v)
                for child in self.children:
                    if child in childrens:
                        continue
                    if child.id == childName:
                        if isinstance(child, ImageField):
                            child.source = v
                        setattr(child, attrName, v)

    def export_to_kv(self, level = 1, save_cm = True, relativ = True, save_relpath = True):
        #Full export, with directives & impacts and bgtemplate
        t,i,d = self.export_field(level, save_cm, relativ, save_relpath)
        #Change the first line
        t[0] =  "%s<%s@BGTemplate>:"%((level-1)*'\t',self.template_name)
        return t,i,d

    def Oexport_field(self, level = 2, save_cm = True, relativ = True, save_relpath = True):
        t,i,d =super(BGTemplate,self).export_field(level, save_cm,relativ,save_relpath)
        #Add specific template case
        BL = self.blank()
        print 'BGT export field', self.vars
        from fields import BaseField
        for pname, editor in self.vars.items():
            print 'vars ', pname
        for fname in self.ids.keys():
            print 'ids', fname
            if not isinstance(self.ids[fname], BaseField):
                continue
            _wid = self.ids[fname]
            if not _wid.editable:
                continue
            if _wid.default_attr:
                print 'current ids default', _wid.default_attr
                me = getattr(_wid, _wid.default_attr)
                blank = getattr(BL.ids[fname],_wid.default_attr)
                if me!= blank:
                    if t[-1] == '':
                        t.pop()
                    print 'match for', fname
                    print 'export of it', _wid.export_field()

                    attr = fname
                    tmpls = t
                    prepend = '\t'*(level)
                    value = me
                    from os.path import relpath, isfile
                    from conf import gamepath
                    from kivy.properties import ObservableDict, ObservableReferenceList, ObservableList
                    from fields import compare_to_root
                    from types import FunctionType
                    from kivy.metrics import cm
                    vtype = type(value)

                    if attr == 'name':
                        tmpls.append('%sid: %s'%(prepend,value))
                    elif  isinstance(value, basestring):
                        if isfile(value) and save_relpath:
                            value = relpath(value, gamepath)
                        tmpls.append('%s%s: "%s"'%(prepend,attr, value))
                    elif vtype == type(1.0):
                        tmpls.append('%s%s: %.2f'%(prepend, attr, value))
                    elif vtype in  (type({}), ObservableDict):
                        for _v in value:
                            try:
                                _uni = unicode(value[_v], 'latin-1')
                            except TypeError: #can not coerce float in latin -1
                                _uni = unicode(value[_v])
                            if isfile(_uni) and save_relpath:
                                value[_v] = relpath(value[_v], gamepath)
                        tmpls.append('%s%s: %s'%(prepend, attr,value))
                    elif vtype in (type(tuple()), type(list()), ObservableList, ObservableReferenceList):
                        if attr in ("size","pos"):
                            if relativ:
                                tmpls.append('%s%s: %s'%(prepend, attr, compare_to_root(self.template.size,value)))
                                continue
                            if save_cm:
                                tmpls.append('%s%s: '%(prepend,attr)+', '.join(["cm(%.2f)"%(v/cm(1)) for v in value]))
                                continue
                        #Looping and removing bracket
                        sub = []
                        for item in value:
                            if isinstance(item, float):
                                sub.append('%.2f'%item)
                            elif isinstance(item, basestring):
                                if isfile(item) and save_relpath:
                                    item = relpath(item, gamepath)
                                sub.append('"%s"'%item)
                            elif isinstance(item, FunctionType): #replace the function by its name without the ""
                                sub.append('%s'%item.func_name)
                            else:
                                sub.append(str(item))
                        if len(sub) != 1:
                            tmpls.append('%s%s: '%(prepend, attr) + ', '.join(sub))
                        else: #only: add a ',' at the end, to have kv understand it is a tuple
                            tmpls.append('%s%s: '%(prepend, attr) + sub[0] + ',')

                    else:
                        tmpls.append('%s%s: %s'%(prepend, attr, value))





        return t,i,d

#Now define the cache foundry for all templates
from kivy._event import EventDispatcher
from kivy.properties import DictProperty

class TemplateList(EventDispatcher):
    templates = DictProperty()

    def copy(self):
        return self.templates.copy()


    def __setitem__(self, key, value):
        #print 'registering template',key
        self.templates[key] = value

    def __getitem__(self,name):
        #If the desired result is a file namee, reload it from file
        res = self.templates[name]
        if isinstance(res, basestring):
            #print 'reloading', res
            return BGTemplate.FromFile(res)[-1]
        return res

    def register(self,tmpl):
        self[tmpl.template_name] = tmpl

    def register_file(self, filename):
        for tmpl in BGTemplate.FromFile(filename):
            self[tmpl.template_name] = tmpl
            tmpl.src = filename
            tmpl.source = 'file'

    def refresh(self, tmplName):
        tmpl = self[tmplName]
        if tmpl.source =='file':
            self.register_file(tmpl.src)
templateList = TemplateList()

#Now for some easy example
class EmptyKlass(BGTemplate):
    def __init__(self,*args,**kwargs):
        BGTemplate.__init__(self)
        self.template_name = "EmptyKlass"
        from fields import ImageField
        img = ImageField()
        #img.x = img.y = 0
        img.id = "default"
        #img.width = self.width
        #img.height = self.height
        img.keep_ratio = True
        img.scale = True
        self.add_widget(img)
        from kivy.metrics import cm
        self.size = (cm(6.35), cm(8.8))
        #img.size = self.size
        #img.size_hint=1,1

#templateList['EmptyKlass'] = EmptyKlass()


class RedSkin(BGTemplate):
    def __init__(self, *args, **kwargs):
        BGTemplate.__init__(self, *args, **kwargs)
        self.template_name = "RedSkinKlass"
        from fields import ColorField
        color = ColorField()
        #color.id = "deffault"
        color.width = self.width
        color.height = self.height
        color.opacity= .5
        color.rgba = (1,0,0,1)
        self.add_widget(color)
        from kivy.metrics import cm
        self.size = color.size = (cm(6.5),cm(8.8))
        from kivy.clock import Clock

#templateList.register(RedSkin())


#Now load all files from the Templates dir to templatelist
def LoadTemplateFolder(folder="Templates"):
    from glob import glob
    from os.path import join
    for kv in glob(join(folder, '*.kv')):
        templateList.register_file(kv)

from conf import CP
if CP.getboolean('Startup', 'LOAD_TMPL_LIB'):
    LoadTemplateFolder()

def find_template_path(filename):
    from os.path import abspath, isfile, join
    from conf import gamepath
    if "@" in filename: #Only using subone
        name, filename = filename.split('@')
    else:
        name = ""
    if not isfile(filename):
        #try with gamepath ?
        if isfile(join(gamepath,path_reader(filename))):
            filename = join(gamepath, path_reader(filename))
    #Here, we convert to abspath / normpath, as filename is used to index rules by kivy. avoid reimporting rules
    filepath = abspath(path_reader(filename))
    filename = filepath
    return name, filename