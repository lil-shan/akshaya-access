"""Everything the agent says: (Malayalam, English) pairs. English is what judges read in the transcript."""

OPENING = (
    "നമസ്കാരം. ഇത് അക്ഷയ ആക്സസ് ആണ്. ഞാൻ ഒരു എ.ഐ. സഹായിയാണ്, മനുഷ്യനല്ല. "
    "ഇത് ഒരു ഡെമോ ആണ്; ഇതിലെ പണമടയ്ക്കൽ യഥാർത്ഥമല്ല, സിമുലേറ്റഡ് ആണ്. "
    "ഈ ഡെമോ കെ.എസ്.ഇ.ബി. ബില്ലും പണമടയ്ക്കലും മാത്രമാണ് ചെയ്യുന്നത്. "
    "നിങ്ങളുടെ ശബ്ദം ഒരു സ്പീച്ച് സേവനം വഴി എഴുത്താക്കി മാറ്റുന്നു. "
    "ഞാൻ ഒരിക്കലും നിങ്ങളുടെ ഒ.ടി.പി., യു.പി.ഐ. പിൻ, ആധാർ നമ്പർ എന്നിവ ചോദിക്കില്ല.",
    "Hello. This is Akshaya Access. I am an AI assistant, not a human. "
    "This is a demo; the payments in it are SIMULATED, not real. "
    "This demo only handles KSEB electricity bills and payments. "
    "Your voice is converted to text by a speech service. "
    "I will never ask for your OTP, UPI PIN or Aadhaar number.",
)
ASK_NUMBER = (
    "നിങ്ങളുടെ കെ.എസ്.ഇ.ബി. കൺസ്യൂമർ നമ്പർ പറയൂ. പതിമൂന്ന് അക്കങ്ങളുണ്ട്; ഓരോ അക്കമായി പതുക്കെ പറയൂ.",
    "Please say your KSEB consumer number. It has 13 digits; say them slowly, one digit at a time.",
)
WRONG_LENGTH = (
    "ക്ഷമിക്കണം, പതിമൂന്ന് അക്കങ്ങൾ വേണം; എനിക്ക് കിട്ടിയത് {n} അക്കങ്ങളാണ്. കൺസ്യൂമർ നമ്പർ ഒന്നുകൂടി പറയൂ.",
    "Sorry, I need 13 digits but I got {n}. Please say the consumer number once more.",
)
READ_BACK_NUMBER = (
    "ഞാൻ കേട്ട നമ്പർ: {digits_ml}. ഇത് ശരിയാണോ? അതെ അല്ലെങ്കിൽ അല്ല എന്ന് പറയൂ.",
    "The number I heard is: {digits_en}. Is this correct? Please say yes or no.",
)
ONLY_YES_NO = (
    "ക്ഷമിക്കണം, മനസ്സിലായില്ല. അതെ അല്ലെങ്കിൽ അല്ല എന്ന് മാത്രം പറയൂ.",
    "Sorry, I did not understand. Please say only yes or no.",
)
NUMBER_AGAIN = (
    "ശരി, നമുക്ക് വീണ്ടും നോക്കാം. കൺസ്യൂമർ നമ്പർ ഒന്നുകൂടി പതുക്കെ പറയൂ.",
    "All right, let us try again. Please say the consumer number once more, slowly.",
)
CHECKING_BILL = ("നന്ദി. ബിൽ പരിശോധിക്കുന്നു, ഒരു നിമിഷം.", "Thank you. Checking the bill, one moment.")
BILL_NOT_FOUND = (
    "ഈ നമ്പറിൽ ഒരു ബിൽ കണ്ടെത്താനായില്ല. കൺസ്യൂമർ നമ്പർ ഒന്നുകൂടി പതുക്കെ പറയൂ.",
    "I could not find a bill for this number. Please say the consumer number once more, slowly.",
)
NOTHING_DUE = (
    "{name} എന്ന പേരിലുള്ള ഈ കണക്ഷനിൽ ഇപ്പോൾ അടയ്ക്കാൻ തുകയൊന്നും ബാക്കിയില്ല. "
    "ഇത് സിമുലേറ്റഡ് ബിൽ ആണ്. പണമടയ്ക്കൽ ആവശ്യമില്ല. വിളിച്ചതിന് നന്ദി.",
    "There is no amount due right now on this connection in the name of {name_en} (SIMULATED bill). "
    "No payment is needed. Thank you for calling.",
)
READ_BACK_BILL = (
    "ബിൽ {name} എന്ന പേരിലാണ്. അടയ്ക്കേണ്ട തുക {amount} രൂപ. "
    "ഇത് സിമുലേറ്റഡ് ബിൽ ആണ്. ഈ പേരും തുകയും ശരിയാണോ, ഈ തുക ഇപ്പോൾ അടയ്ക്കട്ടെ? അതെ അല്ലെങ്കിൽ അല്ല എന്ന് പറയൂ.",
    "The bill is in the name of {name_en}. The amount due is {amount} rupees (SIMULATED bill). "
    "Are the name and amount correct, and shall I start the payment now? Please say yes or no.",
)
DECLINED = (
    "ശരി. പണമടയ്ക്കൽ ഒന്നും നടത്തിയിട്ടില്ല. വിളിച്ചതിന് നന്ദി.",
    "All right. No payment has been made. Thank you for calling.",
)
PIN_HANDOFF = (
    "ഇനി നിങ്ങളുടെ ബാങ്കിന്റെ യു.പി.ഐ. 123പേ ലൈനിൽ, ബാങ്ക് ചോദിക്കുമ്പോൾ, യു.പി.ഐ. പിൻ ഫോണിലെ കീപാഡിൽ അമർത്തുക. "
    "പിൻ ഉറക്കെ പറയരുത്; അത് എനിക്ക് കേൾക്കാൻ കഴിയില്ല, കാണാനും കഴിയില്ല. ഇത് സിമുലേറ്റഡ് ആണ്. ഫലം കിട്ടുന്നതുവരെ ഞാൻ കാത്തിരിക്കാം.",
    "You will now enter your UPI PIN on your phone's keypad with your bank's UPI 123PAY line (SIMULATED). "
    "Do not say the PIN aloud; I cannot hear it or see it. I will wait for the result.",
)
PAID = (
    "പണമടയ്ക്കൽ സ്ഥിരീകരിച്ചു. {amount} രൂപ അടച്ചു. റഫറൻസ് നമ്പർ: {reference}. "
    "ഇത് ഡെമോ ആയതിനാൽ യഥാർത്ഥ പണം കൈമാറിയിട്ടില്ല. വിളിച്ചതിന് നന്ദി.",
    "The payment is confirmed: {amount} rupees paid. Reference: {reference}. "
    "(SIMULATED: no real money moved.) Thank you for calling.",
)
PAYMENT_FAILED = (
    "പണമടയ്ക്കൽ പരാജയപ്പെട്ടു. ബിൽ അടച്ചിട്ടില്ല. ഇത് സിമുലേറ്റഡ് പണമടയ്ക്കൽ ആയിരുന്നു. പിന്നീട് വീണ്ടും ശ്രമിക്കാം. വിളിച്ചതിന് നന്ദി.",
    "The payment failed. The bill has not been paid. You can try again later. Thank you for calling. (SIMULATED payment)",
)
PAYMENT_PENDING = (
    "പണമടയ്ക്കൽ ഇപ്പോഴും പെൻഡിംഗ് ആണ്; അത് നടന്നോ ഇല്ലയോ എന്ന് ഇതുവരെ ഉറപ്പായിട്ടില്ല. "
    "ദയവായി ഇപ്പോൾ വീണ്ടും പണമടയ്ക്കരുത്. ഇത് സിമുലേറ്റഡ് ആണ്. വിളിച്ചതിന് നന്ദി.",
    "The payment is still PENDING; it is not yet known whether it went through. "
    "Please do not pay again right now. (SIMULATED payment) Thank you for calling.",
)
STATUS_UNKNOWN = (
    "പണമടയ്ക്കലിന്റെ സ്ഥിതി പരിശോധിക്കാൻ എനിക്ക് കഴിഞ്ഞില്ല; ഫലം അറിയാൻ കഴിഞ്ഞില്ല. "
    "ദയവായി ഇപ്പോൾ വീണ്ടും പണമടയ്ക്കരുത്. ഇത് സിമുലേറ്റഡ് ആണ്. വിളിച്ചതിന് നന്ദി.",
    "I could not check the payment status, so the result is unknown. "
    "Please do not pay again right now. (SIMULATED payment) Thank you for calling.",
)
TECH_PROBLEM = (
    "ക്ഷമിക്കണം, ഒരു സാങ്കേതിക പ്രശ്നം ഉണ്ടായി. ഈ കോൾ ഇവിടെ അവസാനിപ്പിക്കുന്നു. ഇത് ഡെമോ ആണ്.",
    "Sorry, there was a technical problem. I am ending this call here. (demo)",
)
TECH_PROBLEM_PAYMENT = (
    "ക്ഷമിക്കണം, ഒരു സാങ്കേതിക പ്രശ്നം ഉണ്ടായി. പണമടയ്ക്കൽ നടന്നോ എന്ന് അറിയില്ല. "
    "ദയവായി ഇപ്പോൾ വീണ്ടും പണമടയ്ക്കരുത്. ഇത് സിമുലേറ്റഡ് ആണ്.",
    "Sorry, there was a technical problem. It is not known whether the payment went through. "
    "Please do not pay again right now. (SIMULATED payment)",
)
NOT_PLAYED = (
    "[മുകളിലെ വരി പറഞ്ഞുകേൾപ്പിക്കാൻ കഴിഞ്ഞില്ല]",
    "[The line above was NOT PLAYED to the citizen]",
)
# What the citizen said, as understood: the only form of citizen speech that is posted or shown.
HEARD = {
    "number": ("കൺസ്യൂമർ നമ്പർ {number}", "consumer number {number}"),
    "yes": ("അതെ", "yes"),
    "no": ("അല്ല", "no"),
    "unclear": ("[തിരിച്ചറിയാത്ത സംസാരം]", "[unrecognised speech]"),
    "person": ("ഒരാളോട് സംസാരിക്കണമെന്ന് പറഞ്ഞു", "asked for a person"),
    "service": ("മറ്റൊരു സേവനം ചോദിച്ചു", "asked for another service"),
}
HANDOFF_WHY = {
    "number_unclear": ("ക്ഷമിക്കണം, നമ്പർ എനിക്ക് വ്യക്തമായി മനസ്സിലാക്കാൻ കഴിഞ്ഞില്ല.", "Sorry, I could not get the number clearly."),
    "citizen_request": ("ശരി.", "All right."),
    "unsupported_service": (
        "ക്ഷമിക്കണം, ഈ ഡെമോ കെ.എസ്.ഇ.ബി. വൈദ്യുതി ബില്ലുകൾ മാത്രമേ ചെയ്യൂ.",
        "Sorry, this demo only handles KSEB electricity bills.",
    ),
    "not_played": (
        "ക്ഷമിക്കണം, എന്റെ ശബ്ദം നിങ്ങളെ കേൾപ്പിക്കാൻ കഴിഞ്ഞില്ല.",
        "Sorry, I could not play my voice to you.",
    ),
    "guard": (
        "ക്ഷമിക്കണം, ഒരു സുരക്ഷാ പരിശോധന കാരണം എനിക്ക് ഇത് തുടരാൻ കഴിയില്ല.",
        "Sorry, a safety check stopped me from continuing ({note}).",
    ),
}
HANDOFF = (
    "നിങ്ങളുടെ അഭ്യർത്ഥന അക്ഷയ കേന്ദ്രത്തിലെ ജീവനക്കാർക്കായി രേഖപ്പെടുത്തി. കേസ് നമ്പർ: {case_ml}. "
    "ഇത് ഡെമോ ആയതിനാൽ ഈ കോൾ ഇവിടെ അവസാനിക്കുന്നു; ആരും ഈ ലൈനിൽ തുടരുകയോ വിളിക്കുകയോ ചെയ്യില്ല. നന്ദി.",
    "Your request has been recorded for the Akshaya centre staff. Case number: {case_en}. "
    "This is a demo, so the call ends here; nobody will stay on this line or phone you. Thank you.",
)
