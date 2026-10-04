"""Validate known guide sections before rendering; preserve unknown fields."""
import copy


def prepare_plan(plan, defaults):
    if not isinstance(plan,dict):raise ValueError('Guide must be a JSON object.')
    p=copy.deepcopy(plan)
    defaults=copy.deepcopy(defaults);defaults['meta']['created']=''
    def obj(value):
        if not isinstance(value,dict):raise ValueError('Unsupported guide structure: expected an object.')
        return value
    def rows(value):
        if not isinstance(value,list) or len(value)>500 or any(not isinstance(x,dict) for x in value):
            raise ValueError('Unsupported guide structure: invalid or excessive records.')
        return value
    def strings(value,fields):
        obj(value)
        for key in fields:
            if key in value and not isinstance(value[key],str):raise ValueError('Unsupported guide field: '+key)
    for key,default in defaults.items():
        p.setdefault(key,default)
        if isinstance(default,dict):
            obj(p[key])
            for child,initial in default.items():p[key].setdefault(child,initial)
        elif isinstance(default,list):rows(p[key])
        elif not isinstance(p[key],type(default)):raise ValueError('Unsupported guide field: '+key)
    strings(p['meta'],['app','created','planName','owner','jurisdiction','legalNotes'])
    strings(p['people'],['executor','trustee','helper'])
    for row in rows(p['people']['heirs']):strings(row,['name','relation','role','contact'])
    for section in ['inheritance','rehearsal']:
        strings(p[section],defaults[section].keys())
    strings(p['signing'],['medium','testSpend','coordinatorNotes'])
    if not isinstance(p['signing']['verifyRitual'],list) or any(not isinstance(x,str) for x in p['signing']['verifyRitual']):
        raise ValueError('Unsupported verification checklist.')
    strings(p['backups'],['watchOnly','rescanHeight','sampleAddresses','testedSoftware'])
    for row in rows(p['backups']['descriptorLocations']):strings(row,['where','format'])
    for v in rows(p['vaults']):
        strings(v,['name','tier','script','coordinator','notes','customArchitecture','profileSource','profileReviewed'])
        for key in ['m','n']:
            value=v.get(key)
            if value not in (None,'') and (type(value) is not int or not 1<=value<=100):raise ValueError('Invalid primary signing count.')
        for row in rows(v.setdefault('keys',[])):
            strings(row,['label','device','generation','media','locations','passphrase'])
        if v.get('timelock') is not None:
            strings(v['timelock'],['delay','refreshNote'])
            if 'enabled' in v['timelock'] and type(v['timelock']['enabled']) is not bool:raise ValueError('Invalid timelock flag.')
    for section in ['lawyers','backupRecords','recoveryPaths','accessRecords','instructions']:
        for row in rows(p.setdefault(section,[])):
            if any(not isinstance(x,str) for x in row.values()):raise ValueError('Invalid text record in '+section)
    return p
