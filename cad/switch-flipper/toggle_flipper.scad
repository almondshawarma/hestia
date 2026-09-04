// Non-intrusive toggle-switch flipper (parametric)
// ---------------------------------------------------------------------------
// A bracket that mounts on  existing faceplate screw holes (swap in longer
// M3.5 screws) and holds one servo per gang. The servo horn throws the toggle
// up/down. Fully reversible!
//
// Measure the CAPITALISED params with calipers on YOUR plate, render,
// print, test, iterate. This is a just a rough starting geometry
//
// OpenSCAD because its it's parametric + diffs in
// git, so one file can fit all. Publish this .scad as the source, plus
// exported .stl/.step (see cad/README.md).
// ---------------------------------------------------------------------------

/* [Measure these] */
PLATE_SCREW_SPACING = 83.3;  // mm, vertical distance between the two faceplate screws (1 gang)
GANG_PITCH          = 46.0;  // mm, horizontal center-to-center between adjacent gangs
N_GANGS             = 2;     // fan + light
TOGGLE_LEN          = 12.0;  // mm, how far the bat sticks out past the plate
STANDOFF            = 16.0;  // mm, bracket stand-off from the wall (clears the toggle throw)

/* [Servo, SG90 defaults, use MG90S for stiff switches] */
SERVO_W = 12.6;   // body width
SERVO_L = 22.8;   // body length
SERVO_TAB_SPAN = 32.0;   // hole-to-hole across the mounting tabs
SERVO_TAB_HOLE = 2.0;    // tab screw hole dia

/* [Build] */
WALL = 3.0;              // plate thickness
SCREW_HOLE = 3.8;        // clearance for M3.5 faceplate screws
$fn = 48;

plate_w = (N_GANGS - 1) * GANG_PITCH + 40;   // some margin each side
plate_h = PLATE_SCREW_SPACING + 30;

module screw_holes() {
    for (g = [0 : N_GANGS - 1])
        for (z = [-1, 1])
            translate([g * GANG_PITCH - (N_GANGS-1)*GANG_PITCH/2,
                       z * PLATE_SCREW_SPACING/2, -1])
                cylinder(d = SCREW_HOLE, h = WALL + 2);
}

// servo sits at each gang center and its output shaft over the toggle bat
module servo_pocket() {
    // body cutout
    translate([-SERVO_W/2, -SERVO_L/2, 0])
        cube([SERVO_W, SERVO_L, WALL + 2]);
    // tab screw holes
    for (y = [-1, 1])
        translate([0, y * SERVO_TAB_SPAN/2, -1])
            cylinder(d = SERVO_TAB_HOLE, h = WALL + 2);
}

module mount_plate() {
    difference() {
        // back plate, raised on standoffs so the servos clear the toggles
        union() {
            linear_extrude(WALL)
                offset(r = 4) offset(r = -4)   // rounded corners
                    square([plate_w, plate_h], center = true);
            // standoff bosses around each screw
            for (g = [0 : N_GANGS - 1])
                for (z = [-1, 1])
                    translate([g * GANG_PITCH - (N_GANGS-1)*GANG_PITCH/2,
                               z * PLATE_SCREW_SPACING/2, 0])
                        cylinder(d = 9, h = STANDOFF);
        }
        screw_holes();
        // servo pockets, one per gang, centered vertically
        for (g = [0 : N_GANGS - 1])
            translate([g * GANG_PITCH - (N_GANGS-1)*GANG_PITCH/2, 0, 0])
                servo_pocket();
    }
}

// simple push-arm you can print if the stock servo horn is too short to reach
// the bat. Press-fits on the horn and length reaches TOGGLE_LEN + margin
module push_arm(len = 20) {
    difference() {
        union() {
            cylinder(d = 8, h = 4);                 // hub
            translate([0, -3, 0]) cube([len, 6, 4]); // arm
            translate([len-3, -4, 0]) cube([4, 8, 8]); // fork that hooks the bat
        }
        cylinder(d = 2.5, h = 5);   // horn screw
    }
}

mount_plate();
translate([0, -plate_h/2 - 15, 0]) push_arm();   // printed beside the plate
