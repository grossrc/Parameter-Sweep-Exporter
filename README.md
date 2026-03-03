# Overview
This program assists the user batch export combinations of parameterized designs in the Fusion 360 design software.

Without this program, the user must manually change the parameters driving the model to update then individually save each file (.STL or .STEP). This can be very time consuming, and for certain batch exporting requirements, it's prohibitive. 

This software solves this issue by:
- Automatically exporting bodies as .STEP/.STL files programatically
- Saving the exported files to a batch file folder
- Choosing the interval you want your parameter to be and the number of steps 
    - e.g. Radius should be between 1 mm and 2 mm in 5 increments (exported as 1, 1.25, 1.5, 1.75, 2)
- Automatically computing and assigning compinations of multiple parameter sweeps
    - e.g. sweep radius between 1 and 2mm and sweep length between 5 and 6mm
    - 4 models will export with radii and length: 1/5mm, 1/6mm, 2/5mm, 2/6mm
- Integrating into Fusion's native program environment.
- Custom naming schemes

[![➡️YouTube video Demo⬅️](https://img.youtube.com/vi/IrVTPpV2GpY/0.jpg)](https://youtu.be/IrVTPpV2GpY)

# Importing the program to Fusion
## Option 1 (cleanest)
1) Clone the repo and extract the .ZIP file
2) Place the unzipped folder in your fusion scripts folder. It should be in the directory `C:\Users\yourUserName\AppData\Roaming\Autodesk\Autodesk Fusion 360\API\Scripts`

The program will now automatically load into fusion. You may have to restart fusion or enable the add-in (check box to run on startup) to begin using the program. Simply go to `Utilities > Add-Ins` in the fusion program and enable the program called `ParameterSweepExporter`.

## Option 2 (garaunteed to work)
1) Clone the repo and extract the folder.
2) In Fusion go to `Utilities > Add-Ins` and click the icon. It should look like this:
![alt text](/resources/ScreenshotA.png)
3) In the Add-in window, click the plus symbol. Then click `Script or add-in from device` and select the program folder.
4) Click the dropdown on utilities and run the program in your file that you want to export.
![alt text](/resources/ScreenshotB.png)


## NOTE
To use this program, you must have a parameterized model. In other words, changing your parameter(s) of interest will automatically update the model reflecting that specific change. If you are unfamiliar with parameterization, please find documentation on that before using the program. This is a good introduction (https://www.youtube.com/watch?v=3GQHaYdmULs).

# Relevant Updates
## 3 March 2026
I created a new branch to allow explicit parameter values rather than defining a min/max range and a number of steps (which linearly interpolates values between two endpoints). For example, entering `2, 5, 10, 25` will export at exactly those four values — no more, no less.
