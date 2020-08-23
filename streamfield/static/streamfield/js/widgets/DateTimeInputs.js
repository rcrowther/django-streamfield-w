(function() {
    'use strict'; 

    const NUMERIC = 0
    const ALPHABETA = 2
    var PartData = {
        // time
        'H': {tpe: NUMERIC, len: 2, fprint: 'HH', data: 23},
        'M': {tpe: NUMERIC, len: 2, fprint: 'MM', data: 59},
        'S': {tpe: NUMERIC, len: 2, fprint: 'SS', data: 59},
        // date
        'd': {tpe: NUMERIC, len: 2, fprint: 'DD', data: 31},
        'j': {tpe: NUMERIC, len: 3, fprint: 'DDD', data: 366},
        'U': {tpe: NUMERIC, len: 2, fprint: 'WW', data: 53},
        'W': {tpe: NUMERIC, len: 2, fprint: 'WW', data: 53},
        'm': {tpe: NUMERIC, len: 2, fprint: 'MM', data: 12},
        'y': {tpe: NUMERIC, len: 2, fprint: 'YY', data: 99},
        'Y': {tpe: NUMERIC, len: 4, fprint: 'YYYY', data: 9999},
        // alphabetic times
        'a': {tpe: ALPHABETA, len: 3, fprint: 'ddd', data: {
                mon: {auto: 'm'},
                tue: {auto: 'tu'},  
                wed: {auto: 'w'},
                thu: {auto: 'th'},
                fri: {auto: 'f'},
                sat: {auto: 'sa'},
                sun: {auto: 'su'},
                }},
        'b': {tpe: ALPHABETA, len: 3, fprint: 'mmm', data: {
                jan: {auto: 'j'},
                feb: {auto: 'f'},  
                mar: {auto: 'mar'},
                apr: {auto: 'ap'},
                may: {auto: 'may'},
                jun: {auto: 'jun'},
                jul: {auto: 'jul'},
                aug: {auto: 'au'},  
                sep: {auto: 's'},
                oct: {auto: 'o'},
                nov: {auto: 'n'},
                dec: {auto: 'd'},
                }},
    }

    function autoMap(obj) {
        const r = {};
        Object.keys(obj).forEach(key => {
            r[obj[key]['auto']] = key
        })
        return r
    }
    
    function formatParse(fmt) {
        let toks = []
        let dlms = []
        let i = 0;
        let c = ''
        let dlm = ''
        while (i < fmt.length) {
            c = fmt[i]
            if (c == '%') {
                dlms.push( dlm )
                dlm = ''
                toks.push(fmt[i+1])
                i++
            } else {
                dlm += c
            }
            i++
        }
        return {tokenIds: toks, delimiters: dlms.slice(1) }
    }

    class Parser {
        constructor(fInfo) {
            var i = 0
            var chain = []
            var partNames = []
            for (const pid of fInfo.tokenIds) {
                if (pid in PartData) {
                    const d = PartData[pid]
                    const l = d.len
                    switch(d.tpe){
                        case NUMERIC:
                            chain.push(new PartNumParse(pid, i, l, d.data))
                            break
                        case ALPHABETA:
                            chain.push(new PartTextParse(pid, i, l, Object.keys(d.data), autoMap(d.data)))
                            break
                        default:
                            throw "Format type not recognised. code: " + d.tpe
                    }
                    partNames.push(d.fprint)
                    i += l

                } else {
                    throw "Part of format not recognised. part:'" + pid + "'"
                }
            }
            this.placeholder = this.interspace(partNames, fInfo.delimiters)
            this.pLen = i
            this.chain = chain
            this.prevLen = 0
        }
        
        delimit(v, seps) {
            let l = v.length
            let b = []
            let i = 0
            let nextSep = ''
            for (const e of this.chain) {
                nextSep = seps[i]
                i++
                const to = e.to
                b.push(v.slice(e.from, to))
                if (l <= to) {
                    if (l == to && l < this.pLen) { b.push(nextSep) }
                    break;
                }
                b.push(nextSep) 
            }
            return b.join('')
        }
        
        interspace(ex, seps) {
            const b = []
            let i = 0
            let l = seps.length
            while(i < l){
                b.push(ex[i])
                b.push(seps[i])
                i++
            }
            b.push(ex[i])
            return b.join('')
        }
        
        prepare(v) {
            //v = v.replace(this.regex,'')
            v =  v.replace(/[^\w]/g, '')
            v = v.slice(0, this.pLen)
            return v
        }
        
        clean(v) {
            for (const e of this.chain) {
                    v = e.clean(v)
            }
            return v
        }
        
        fclean(v, seps) {
            const l = v.length
            if (this.prevLen > l) {
                this.prevLen = l
                return v
            }
            v = this.prepare(v)
            v = this.clean(v)
            v = this.delimit(v, seps)
            this.prevLen = v.length 
            return v
        }
    }
    
    class PartNumParse {
        constructor(p, from, len, max) {
            this.part = p
            this.from = from
            this.len = len
            this.to = from + len
            this.max = max
        }
        clean(v) {
            const l = v.length
            if (l < this.from) {
                return v
            }
            let tok = v.slice(this.from, this.to)
            tok = tok.replace(/[^\d]/g, '')
            const ft = tok + "0".repeat(this.len - tok.length)
            if (+ft > this.max) { 
                tok = '0' + tok
            }
            return v.slice(0, this.from) + tok + v.slice(this.to)
        }
    }

    class PartTextParse {
        constructor(p, from, len, opts, auto) { 
            this.part = p
            this.from = from
            this.len = len
            this.to = from + len
            this.opts = opts
            this.auto = auto
        }
        
        clean(v) {
            const l = v.length
            if (l < this.from) {
                return v
            }
            var tok = v.slice(this.from, this.to)
            tok = tok.replace(/\d/g, '')

            if (tok.length < this.len) {
                const full = this.auto[tok]
                if (full) { tok = full }
            } else {
                if (this.opts.indexOf(tok.toLowerCase()) == -1) { tok = '' }
            }
            return v.slice(0, this.from) + tok + v.slice(this.to)
        }
    }


    var DateTimeInputs = {
 
        enable: function(e, format) {
            if (!(e && e.nodeName && e.nodeName === 'INPUT')) {
                return;
            };

            const fInfo = formatParse(format)

            const ps = new Parser(fInfo)
            e.setAttribute("placeholder", ps.placeholder)

            e.addEventListener("input", function(e) {
                e.preventDefault()
                e.stopPropagation()
                e.currentTarget.value = ps.fclean(e.target.value, fInfo.delimiters)
            });
        },
        
    };
    
    window.DateTimeInputs = DateTimeInputs;
})();
