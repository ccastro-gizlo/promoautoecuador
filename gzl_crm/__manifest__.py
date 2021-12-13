{
    "name" : "gzl_crm",
    "version" : "0.1",
    'depends' :['crm','sale',
                ],
    "author" : "Yadira Quimis Gizlo",
    "description" : """
    Heredado de CRM
                    """,
    "website" : "http://www.gizlocorp.com",
    "category" : "Generic Modules",
   
    "data" : [   
                "data/data_accion_planificada.xml",
                "security/ir.model.access.csv",
                "views/crm_lead_view.xml", 
                "views/crm_lead_simplified_form.xml", 
                "wizard/wizard_cuota_pago_amortizacion.xml",                    
            ],
    
    'installable': True,
    'auto_install': False,
}



