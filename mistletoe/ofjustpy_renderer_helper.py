import functools
from addict import Dict
import ofjustpy as oj

from typing import Any, NamedTuple

# def chainme(func):
#     @functools.wraps(func)
#     def wrapper(*args, **kwargs):
#         renderer_obj = args[0]
#         token = args[1]
#         res = func(*args, **kwargs)
#         return res

#     return wrapper



def captureViewDirective(func):
    """
    L6 headings are view directives; should be removed from rendering 
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        renderer_obj = args[0]
        token = args[1]
        if token.level == 6:
            renderer_obj.parsing_in_meta_mode = True
            inner = [_ for _ in renderer_obj.render_inner(token) if _ is not None]
            renderer_obj.parsing_in_meta_mode = False
            view_directive = inner[0].rawText
            handler_type, handler_funcname = view_directive.split(":")
            if handler_funcname != 'None':
                renderer_obj.mditem_view_handlers[handler_type] = renderer_obj.mdview_funclookup[handler_funcname]
            else:
                renderer_obj.mditem_view_handlers[handler_type] = None

            #print ("adding view directive = ", handler_type, " ",  handler_funcname) 

            return
        else:
            return func(*args, **kwargs)

    return wrapper

# all about context of mditems
ctx_depth = 0

class ctx(NamedTuple):
    ctxtype: Any
    ctxhandle: Any

def pop_covering_ctx(covering_ctx_stack, ctxtype):
    global ctx_depth
    last_ctx = covering_ctx_stack.pop()
    spaces = "".join([" " for i in range(ctx_depth)])
    #print (f"{spaces} </{last_ctx.ctxtype}>")
    ctx_depth -= 1
    while True:
        if not covering_ctx_stack:
            break
        if last_ctx.ctxtype == ctxtype:
            break
        last_ctx = covering_ctx_stack.pop()
        spaces = "".join([" " for i in range(ctx_depth)])
        #print (f"{spaces} </{last_ctx.ctxtype}>")
        ctx_depth -= 1

        
def append_covering_ctx(covering_ctx_stack, ctxtype,  ctxhandle):
    """
    context_handle == None implies a closed context 
    """
    global ctx_depth
    needs_pop  = False
    # check if ctx appears earlier
    for ctxitem in covering_ctx_stack:
        if ctxitem.ctxtype == ctxtype:
            needs_pop = True

    if needs_pop:
        pop_covering_ctx(covering_ctx_stack, ctxtype)
    #spaces = "".join([" " for i in range(ctx_depth)])
    #print(f"{spaces} <", ctxtype, ">")

    covering_ctx_stack.append(ctx(ctxtype,  ctxhandle))
    ctx_depth += 1

        
def attach_to_covering_ctx(covering_ctx_stack, ref):
    print("&&&&>>>>. attach to covering context ", ref.hcgen)
    print ("covering_ctx_stack = ", covering_ctx_stack)
    top_ctx = covering_ctx_stack[-1]
    if top_ctx.ctxhandle is None:
        print ("&&&& not attached since last context is None")
        return ref
    else:
        print("&&&&>>>>. attach to covering context")
        print (f"{ref.key} is-attached-to {top_ctx.ctxhandle.key}")
        top_ctx.ctxhandle.cgens.append(ref)
        return None
    
def openCtx(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        renderer_obj = args[0]
        token = args[1]
        print ("---begin:openCtx --: for func = ", func, " token = ", token)
        mditem_ctxstack = renderer_obj.mditem_ctxstack
        mditem_name = func.__name__.replace("render_", "")
        if mditem_name == "heading":
            mditem_name += str(token.level)
        
        key_cursor = 0
        head_ref = oj.StackV_(f"{mditem_name}_{key_cursor}", cgens = [], pcp=["md:w-4/5"])
        append_covering_ctx(mditem_ctxstack,  mditem_name,  head_ref)
        res = func(*args, content_stub=head_ref,  **kwargs)
        return res

    return wrapper


def openCloseCtx(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print ("==>begin<== openCloseCtx wrapper invoked for func ", func)
        renderer_obj = args[0]
        token = args[1]

        mditem_ctxstack = renderer_obj.mditem_ctxstack
        mditem_name = func.__name__.replace("render_", "")
        if mditem_name == "heading":
            mditem_name += str(token.level)
        
        key_cursor = 0
        append_covering_ctx(mditem_ctxstack,  mditem_name,  None)
        hcstub = func(*args,  **kwargs)
        pop_covering_ctx(mditem_ctxstack, mditem_name)
        print ("what the hell is mditem_ctxstack = ", mditem_ctxstack)
        # no element covers document covering context
        if mditem_name != "document":
            hcstub = attach_to_covering_ctx(mditem_ctxstack, hcstub)
        print ("==>finished<== openCloseCtx wrapper invoked for func ", func)
        return hcstub

    return wrapper



def renderDictOrHC(func):
    """
    takes a misltetoe orig render function but changes
    rendering to dict or oj
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print ("~~BEGIN~~~Calling renderDictOrHC for func = ", func)
        renderer_obj = args[0]
        token = args[1]
        mditem_ctxstack = renderer_obj.mditem_ctxstack
        mditem_name = func.__name__.replace("render_", "")
        view_func_name = mditem_name + "_view_handler"
        collect_as_dict = True
        
        # if the child has its own viewer function then deploy
        # that instead of collecting the text
        
        if view_func_name in renderer_obj.mditem_view_handlers:
            if renderer_obj.mditem_view_handlers[view_func_name]:
                collect_as_dict = False
        
        if renderer_obj.parsing_in_meta_mode and collect_as_dict:
            #don't create htmlcomponent
            #simply return all attributes as Dict object
            res = func(*args, asdict=True)
            print ("~~END-asdict~~~Calling renderDictOrHC for func = ", func)
            return res
        else:
            
            if view_func_name in renderer_obj.mditem_view_handlers:
                if renderer_obj.mditem_view_handlers[view_func_name]:
                    # build a dict of the subtree dom
                    # and pass the dict to the viewer function
                    renderer_obj.parsing_in_meta_mode = True
                    content_dict = [renderer_obj.render(child) for child in  token.children]
                    res = Dict({mditem_name: content_dict})
                    renderer_obj.parsing_in_meta_mode = False
                    mditem_view_stub = renderer_obj.mditem_view_handlers[view_func_name](res, renderer_obj.key_cursor)
                    renderer_obj.key_cursor += 1
                    print ("~~END-patanahi~~~Calling renderDictOrHC for func = ", func)
                    return attach_to_covering_ctx(mditem_ctxstack,  mditem_view_stub)


            #create html component stub
            hcstub = func(*args, **kwargs)
            # we cannot attach to covering context here
            # this mditem may itself have opened its own context
            # in a sense we are trying to attach to itself.
            # do the attachement after openCloseCtx
            # hcstub = attach_to_covering_ctx(mditem_ctxstack, hcstub)
            # print ("~~END-as-hcstub~~~Calling renderDictOrHC for func = ", func)
            return hcstub
        #return inner

    return wrapper
