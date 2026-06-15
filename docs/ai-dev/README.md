## AI Tools 

|   Tool    |  Usage                                                                |
| --------  | --------------------------------------------------------------------- |
| ChatGPT   |   1. Brainstorming the idea and features (Research)           <br>    |
|           |   2. Debugging issues and understanding error messages         <br>   |
| Qwen      |   1. Development of initial prototype with frontend and backend components <br>|
|           |   2. Prompts for Gemini AI model used in the application <br>         |
| Claude    |   1. FastAPI based backend development     <br>                       |
|           |   2. Authentication and user management feature implementatoin<br>    |


## Development Approach with AI 

### Brainstorming
The initial idea was brainstormed with ChatGPT where I discussed on the below,
1. What are the different methods in which logs can be analyzed?
2. Which is the most efficient method to parse unstructured logs?
3. How can LLM identify a solution and provide mitigation plan without hallucinating?

This brainstorming helped me in identifying a list of different algorithms that can be used for log parsing and I chose Drain algorithm based on its simplicity.

### Plan
Once the idea and the required features were decided, ChatGPT was used in planning the tech stack, architecture and the overall design of the application. Unfortunately, ChatGPT was good in creating the plan but not ideal in implementing it.

### Initial implementation
A carefully crafted prompt was designed and given to Qwen to create the initial boilertemplate of the application. The prompt contained the below details,
1. Goal of the application
2. List of features necessary in the initial prototype
3. Details about the algorithm to be used to convert unstructured logs into structured output
4. Tech stack for the backend
5. Gemini API for AI model in the application
6. Structured response from Gemini API service

### Improving the prototype
The initial prototype did not implement database, authentication and user management. This was later implemented using Claude, ChatGPT and Qwen. Each of the features were implemented separately with clearly defined instructions to the LLMs.

1. Database
PostgreSQL was chosen for its simplicity and for a relational database. The database was not hosted to a quick prototype and runs locally on the device.

2. Authentication
bcrypt was used for authentication of users in this application. 

3. User management
Authentication along with user details stored in the database were combined to implement user management. The details about the user's org were stored in the database along with their email, hashed password, org_id and the org_role.

### Fixing issues
Some of the issues observed during the development of this application are listed below,
1. Absence of proper database implementation
2. User management and authentication were missing
3. Org user management did not work due to invalid FastAPI endpoints 

The above issues were later identified and fixed individually.

## Reflection 

### What worked?
AI tools mentioned above were great in brainstorming ideas, features, implementing a good initial prototype which drastically reduced the development time. 
They were also good in identifying the root cause of different errors and assisted in debugging.

The tools were also good in generating prompts for the AI service within the application and the response of the AI API service was properly structured.

### What failed?
AI tools were not very good in identifying problems listed below,
1. Missing database implementation
2. Missing critical features like user management and authentication
3. Duplicate and invalid fastapi endpoints which broke the org user management feature

### Changes made and the rationale
After identifying each of the problems above, the prompts to the AI tools were modified by me where I first brainstormed the possible solutions, identified each one's advantages and disadvantages and then implemented the best solution for my requirement.


1. Missing database implementation
Using Claude, a local on device postgresql database was designed and implemented which helped in implementing the user management related features and storing of the results of previously analyzed logs.

2. Missing features like user management and authentication
Claude and Qwen were used in implementing the missing features related to authentication and user management. In order to solve each of them, the problems were separated and implemented individually. As part of authentication, the signup and login pages were fixed and the user management was implemented by adding a new table in the database which stored user information.

3. Duplicate and invalid fastapi endpoints
Org user management did not work as expected and there were errors displayed everytime the users page was opened. This was due to duplicate and invalid fastapi endpoints added by the AI model. On identification, the duplicate endpoints were removed.

